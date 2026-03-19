import asyncio
import json
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from models.schema import get_db
from services.face_detection import process_single_photo
from services.clustering import load_embeddings, cluster_faces, get_cluster_stats
from services.age_estimation import estimate_age

router = APIRouter()

DATA_DIR = os.environ.get("DATA_DIR", "/data")

# Processing lock to prevent concurrent runs
_processing_lock = asyncio.Lock()


@router.post("/process")
async def start_processing():
    """Trigger face detection, embedding extraction, and clustering."""
    if _processing_lock.locked():
        raise HTTPException(status_code=409, detail="Processing already in progress")

    return {"status": "started", "stream_url": "/api/photos/process/stream"}


@router.get("/process/stream")
async def process_stream():
    """SSE stream for processing progress."""

    async def event_generator():
        if _processing_lock.locked():
            yield {"event": "error", "data": json.dumps({"error": "Processing already in progress"})}
            return

        async with _processing_lock:
            db = await get_db()
            try:
                # Get unprocessed photos
                cursor = await db.execute(
                    "SELECT id, stored_filename FROM photos WHERE processed = 0"
                )
                photos = await cursor.fetchall()
                total = len(photos)

                if total == 0:
                    # Check if we have any photos at all
                    cursor = await db.execute("SELECT COUNT(*) FROM photos")
                    count = (await cursor.fetchone())[0]
                    if count == 0:
                        yield {"event": "error", "data": json.dumps({"error": "No photos uploaded yet"})}
                        return
                    yield {"event": "info", "data": json.dumps({"message": "All photos already processed. Re-running clustering..."})}

                yield {
                    "event": "start",
                    "data": json.dumps({"total": total, "phase": "face_detection"}),
                }

                # Phase 1: Face detection + embedding extraction
                all_faces_for_clustering = []
                semaphore = asyncio.Semaphore(3)  # Concurrency limit

                async def process_with_limit(photo_id, filename, index):
                    async with semaphore:
                        try:
                            faces = await process_single_photo(photo_id, filename)
                            # Store faces in DB
                            for face in faces:
                                await db.execute(
                                    """INSERT OR REPLACE INTO faces
                                       (id, photo_id, crop_path, embedding_path,
                                        bbox_x, bbox_y, bbox_w, bbox_h, confidence)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                    (
                                        face["face_id"],
                                        photo_id,
                                        face["crop_path"],
                                        face.get("embedding_path", ""),
                                        face["bbox"]["x"],
                                        face["bbox"]["y"],
                                        face["bbox"]["w"],
                                        face["bbox"]["h"],
                                        face["confidence"],
                                    ),
                                )

                                if face.get("embedding_path"):
                                    all_faces_for_clustering.append({
                                        "face_id": face["face_id"],
                                        "embedding_path": face["embedding_path"],
                                        "photo_id": photo_id,
                                    })

                            await db.execute(
                                "UPDATE photos SET processed = 1 WHERE id = ?",
                                (photo_id,),
                            )
                            await db.commit()

                            return {
                                "photo_id": photo_id,
                                "faces_found": len(faces),
                                "index": index,
                            }
                        except asyncio.TimeoutError:
                            return {
                                "photo_id": photo_id,
                                "faces_found": 0,
                                "index": index,
                                "error": "timeout",
                            }
                        except Exception as e:
                            return {
                                "photo_id": photo_id,
                                "faces_found": 0,
                                "index": index,
                                "error": str(e),
                            }

                # Process in batches for progress reporting
                for i, photo in enumerate(photos):
                    result = await process_with_limit(photo[0], photo[1], i)
                    yield {
                        "event": "progress",
                        "data": json.dumps({
                            "phase": "face_detection",
                            "current": i + 1,
                            "total": total,
                            "detail": result,
                        }),
                    }

                # Also include already-processed faces for clustering
                cursor = await db.execute(
                    "SELECT id as face_id, embedding_path, photo_id FROM faces WHERE embedding_path != ''"
                )
                existing_faces = await cursor.fetchall()
                existing_face_ids = {f["face_id"] for f in all_faces_for_clustering}
                for row in existing_faces:
                    if row[0] not in existing_face_ids:
                        all_faces_for_clustering.append({
                            "face_id": row[0],
                            "embedding_path": row[1],
                            "photo_id": row[2],
                        })

                # Phase 2: Clustering
                yield {
                    "event": "phase",
                    "data": json.dumps({"phase": "clustering", "total_faces": len(all_faces_for_clustering)}),
                }

                if len(all_faces_for_clustering) > 0:
                    face_ids, embeddings = load_embeddings(all_faces_for_clustering)

                    if len(face_ids) > 0:
                        assignments = cluster_faces(face_ids, embeddings)

                        # Clear old clusters
                        await db.execute("DELETE FROM clusters")
                        await db.execute("UPDATE faces SET cluster_id = NULL, is_target = 0")

                        # Store cluster assignments
                        cluster_counts = {}
                        for face_id, cluster_id in assignments.items():
                            if cluster_id >= 0:
                                await db.execute(
                                    "UPDATE faces SET cluster_id = ? WHERE id = ?",
                                    (cluster_id, face_id),
                                )
                                cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

                        for cluster_id, count in cluster_counts.items():
                            await db.execute(
                                "INSERT INTO clusters (id, face_count) VALUES (?, ?)",
                                (cluster_id, count),
                            )

                        await db.commit()

                        stats = get_cluster_stats(assignments)
                        yield {
                            "event": "clustering_done",
                            "data": json.dumps({
                                "clusters": stats,
                                "total_faces": len(face_ids),
                                "unclustered": sum(1 for v in assignments.values() if v == -1),
                            }),
                        }
                    else:
                        yield {
                            "event": "clustering_done",
                            "data": json.dumps({"clusters": [], "total_faces": 0, "unclustered": 0}),
                        }
                else:
                    yield {
                        "event": "clustering_done",
                        "data": json.dumps({"clusters": [], "total_faces": 0, "unclustered": 0}),
                    }

                yield {
                    "event": "complete",
                    "data": json.dumps({"status": "done"}),
                }

            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)}),
                }
            finally:
                await db.close()

    return EventSourceResponse(event_generator())


@router.get("/clusters")
async def get_clusters():
    """Get face clusters with representative face crops."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, face_count, is_target, confirmed_at FROM clusters ORDER BY face_count DESC"
        )
        clusters = await cursor.fetchall()

        result = []
        for cluster in clusters:
            # Get face crops for this cluster
            cursor2 = await db.execute(
                """SELECT f.id, f.crop_path, f.photo_id, f.confidence
                   FROM faces f
                   WHERE f.cluster_id = ?
                   ORDER BY f.confidence DESC""",
                (cluster[0],),
            )
            faces = await cursor2.fetchall()

            result.append({
                "cluster_id": cluster[0],
                "face_count": cluster[1],
                "is_target": bool(cluster[2]),
                "confirmed_at": cluster[3],
                "faces": [
                    {
                        "face_id": f[0],
                        "crop_url": f"/data/{f[1]}",
                        "photo_id": f[2],
                        "confidence": f[3],
                    }
                    for f in faces
                ],
            })

        return {"clusters": result}
    finally:
        await db.close()


@router.post("/clusters/{cluster_id}/confirm")
async def confirm_cluster(cluster_id: int):
    """Confirm a cluster as the target person."""
    db = await get_db()
    try:
        # Reset any previous target
        await db.execute("UPDATE clusters SET is_target = 0, confirmed_at = NULL")
        await db.execute("UPDATE faces SET is_target = 0")

        # Set new target
        await db.execute(
            "UPDATE clusters SET is_target = 1, confirmed_at = datetime('now') WHERE id = ?",
            (cluster_id,),
        )
        await db.execute(
            "UPDATE faces SET is_target = 1 WHERE cluster_id = ?",
            (cluster_id,),
        )
        await db.commit()

        # Get the count
        cursor = await db.execute(
            "SELECT COUNT(*) FROM faces WHERE cluster_id = ?", (cluster_id,)
        )
        count = (await cursor.fetchone())[0]

        return {"status": "confirmed", "cluster_id": cluster_id, "face_count": count}
    finally:
        await db.close()


@router.post("/estimate-ages")
async def estimate_ages():
    """Run age estimation on all target person face crops."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT f.id, f.crop_path, f.photo_id
               FROM faces f
               WHERE f.is_target = 1"""
        )
        target_faces = await cursor.fetchall()

        if not target_faces:
            raise HTTPException(status_code=400, detail="No target person confirmed yet")

        results = []
        for face in target_faces:
            face_id = face[0]
            crop_path = face[1]
            photo_id = face[2]

            age = await estimate_age(crop_path)
            if age is not None:
                await db.execute(
                    """INSERT OR REPLACE INTO age_estimates
                       (photo_id, face_id, estimated_age, method)
                       VALUES (?, ?, ?, 'deepface')""",
                    (photo_id, face_id, age),
                )
                results.append({
                    "photo_id": photo_id,
                    "face_id": face_id,
                    "estimated_age": age,
                })

        await db.commit()
        return {"estimates": results, "count": len(results)}
    finally:
        await db.close()
