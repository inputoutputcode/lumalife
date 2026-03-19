import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from models.schema import get_pool, get_or_create_user, get_user_dir, _sanitize_username
from services.face_detection import process_single_photo
from services.clustering import load_embeddings, cluster_faces, get_cluster_stats
from services.age_estimation import estimate_age

router = APIRouter()

# Processing locks per user
_processing_locks: dict[str, asyncio.Lock] = {}


def _get_lock(username: str) -> asyncio.Lock:
    if username not in _processing_locks:
        _processing_locks[username] = asyncio.Lock()
    return _processing_locks[username]


@router.post("/process")
async def start_processing(request: Request):
    username = request.state.username
    _processing_lock = _get_lock(username)
    """Trigger face detection, embedding extraction, and clustering."""
    if _processing_lock.locked():
        raise HTTPException(status_code=409, detail="Processing already in progress")

    return {"status": "started", "stream_url": "/api/photos/process/stream"}


@router.get("/process/stream")
async def process_stream(request: Request, user: str | None = None):
    """SSE stream for processing progress."""
    # SSE (EventSource) can't send headers, so accept user from query param too
    username = user if user else request.state.username
    username = _sanitize_username(username)
    user_id = await get_or_create_user(username)
    user_dir = get_user_dir(username)
    _processing_lock = _get_lock(username)

    async def event_generator():
        if _processing_lock.locked():
            yield {"event": "error", "data": json.dumps({"error": "Processing already in progress"})}
            return

        async with _processing_lock:
            pool = await get_pool()
            async with pool.acquire() as conn:
                try:
                    # Get unprocessed photos
                    photos = await conn.fetch(
                        "SELECT id, stored_filename FROM photos WHERE user_id = $1 AND processed = FALSE",
                        user_id,
                    )
                    total = len(photos)

                    if total == 0:
                        # Check if we have any photos at all
                        count = await conn.fetchval(
                            "SELECT COUNT(*) FROM photos WHERE user_id = $1", user_id
                        )
                        if count == 0:
                            yield {"event": "error", "data": json.dumps({"error": "No photos uploaded yet"})}
                            return
                        yield {"event": "info", "data": json.dumps({"message": "All photos already processed. Re-running clustering..."})}

                    yield {
                        "event": "start",
                        "data": json.dumps({"total": total, "phase": "face_detection"}),
                    }

                    # Phase 1: Face detection + embedding extraction
                    for i, photo in enumerate(photos):
                        photo_id = photo["id"]
                        filename = photo["stored_filename"]
                        try:
                            faces = await process_single_photo(photo_id, filename, user_dir)
                            # Store faces in DB
                            for face in faces:
                                embedding = face.get("embedding")
                                embedding_str = None
                                if embedding is not None:
                                    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

                                await conn.execute(
                                    """INSERT INTO faces
                                       (id, photo_id, crop_path,
                                        bbox_x, bbox_y, bbox_w, bbox_h, confidence, embedding)
                                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector)
                                       ON CONFLICT (id) DO UPDATE SET
                                           crop_path = $3, bbox_x = $4, bbox_y = $5,
                                           bbox_w = $6, bbox_h = $7, confidence = $8,
                                           embedding = $9::vector""",
                                    face["face_id"],
                                    photo_id,
                                    face["crop_path"],
                                    face["bbox"]["x"],
                                    face["bbox"]["y"],
                                    face["bbox"]["w"],
                                    face["bbox"]["h"],
                                    face["confidence"],
                                    embedding_str,
                                )

                            await conn.execute(
                                "UPDATE photos SET processed = TRUE WHERE id = $1",
                                photo_id,
                            )

                            result = {
                                "photo_id": photo_id,
                                "faces_found": len(faces),
                                "index": i,
                            }
                        except asyncio.TimeoutError:
                            result = {
                                "photo_id": photo_id,
                                "faces_found": 0,
                                "index": i,
                                "error": "timeout",
                            }
                        except Exception as e:
                            result = {
                                "photo_id": photo_id,
                                "faces_found": 0,
                                "index": i,
                                "error": str(e),
                            }

                        yield {
                            "event": "progress",
                            "data": json.dumps({
                                "phase": "face_detection",
                                "current": i + 1,
                                "total": total,
                                "detail": result,
                            }),
                        }

                    # Load all faces with embeddings for this user (for clustering)
                    all_face_rows = await conn.fetch(
                        """SELECT f.id as face_id, f.embedding::text as embedding
                           FROM faces f
                           JOIN photos p ON f.photo_id = p.id
                           WHERE p.user_id = $1 AND f.embedding IS NOT NULL""",
                        user_id,
                    )
                    all_faces_for_clustering = [
                        {"face_id": r["face_id"], "embedding": r["embedding"]}
                        for r in all_face_rows
                    ]

                    # Phase 2: Clustering
                    yield {
                        "event": "phase",
                        "data": json.dumps({"phase": "clustering", "total_faces": len(all_faces_for_clustering)}),
                    }

                    if len(all_faces_for_clustering) > 0:
                        face_ids, embeddings = load_embeddings(all_faces_for_clustering)

                        if len(face_ids) > 0:
                            assignments = cluster_faces(face_ids, embeddings)

                            # Clear old clusters for this user
                            await conn.execute("DELETE FROM clusters WHERE user_id = $1", user_id)
                            await conn.execute(
                                """UPDATE faces SET cluster_id = NULL, is_target = FALSE
                                   WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)""",
                                user_id,
                            )

                            # Store cluster assignments
                            cluster_counts = {}
                            for face_id, cluster_id in assignments.items():
                                if cluster_id >= 0:
                                    await conn.execute(
                                        "UPDATE faces SET cluster_id = $1 WHERE id = $2",
                                        cluster_id, face_id,
                                    )
                                    cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

                            for cluster_id, count in cluster_counts.items():
                                await conn.execute(
                                    "INSERT INTO clusters (id, user_id, face_count) VALUES ($1, $2, $3)",
                                    cluster_id, user_id, count,
                                )

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

    return EventSourceResponse(event_generator())


@router.get("/clusters")
async def get_clusters(request: Request):
    """Get face clusters with representative face crops."""
    user_id = request.state.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        clusters = await conn.fetch(
            "SELECT id, face_count, is_target, confirmed_at FROM clusters WHERE user_id = $1 ORDER BY face_count DESC",
            user_id,
        )

        result = []
        for cluster in clusters:
            faces = await conn.fetch(
                """SELECT f.id, f.crop_path, f.photo_id, f.confidence
                   FROM faces f
                   WHERE f.cluster_id = $1
                     AND f.photo_id IN (SELECT id FROM photos WHERE user_id = $2)
                   ORDER BY f.confidence DESC""",
                cluster["id"], user_id,
            )

            result.append({
                "cluster_id": cluster["id"],
                "face_count": cluster["face_count"],
                "is_target": cluster["is_target"],
                "confirmed_at": cluster["confirmed_at"].isoformat() if cluster["confirmed_at"] else None,
                "faces": [
                    {
                        "face_id": f["id"],
                        "crop_url": f"/data/{f['crop_path']}",
                        "photo_id": f["photo_id"],
                        "confidence": f["confidence"],
                    }
                    for f in faces
                ],
            })

        return {"clusters": result}


@router.post("/clusters/{cluster_id}/confirm")
async def confirm_cluster(cluster_id: int, request: Request):
    """Confirm a cluster as the target person."""
    user_id = request.state.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Reset any previous target for this user
            await conn.execute(
                "UPDATE clusters SET is_target = FALSE, confirmed_at = NULL WHERE user_id = $1",
                user_id,
            )
            await conn.execute(
                "UPDATE faces SET is_target = FALSE WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )

            # Set new target
            await conn.execute(
                "UPDATE clusters SET is_target = TRUE, confirmed_at = NOW() WHERE id = $1 AND user_id = $2",
                cluster_id, user_id,
            )
            await conn.execute(
                """UPDATE faces SET is_target = TRUE
                   WHERE cluster_id = $1
                     AND photo_id IN (SELECT id FROM photos WHERE user_id = $2)""",
                cluster_id, user_id,
            )

        # Get the count
        count = await conn.fetchval(
            """SELECT COUNT(*) FROM faces
               WHERE cluster_id = $1
                 AND photo_id IN (SELECT id FROM photos WHERE user_id = $2)""",
            cluster_id, user_id,
        )

        return {"status": "confirmed", "cluster_id": cluster_id, "face_count": count}


@router.post("/estimate-ages")
async def estimate_ages(request: Request):
    """Run age estimation on all target person face crops."""
    username = request.state.username
    user_id = request.state.user_id
    user_dir = get_user_dir(username)
    pool = await get_pool()
    async with pool.acquire() as conn:
        target_faces = await conn.fetch(
            """SELECT f.id, f.crop_path, f.photo_id
               FROM faces f
               JOIN photos p ON f.photo_id = p.id
               WHERE f.is_target = TRUE AND p.user_id = $1""",
            user_id,
        )

        if not target_faces:
            raise HTTPException(status_code=400, detail="No target person confirmed yet")

        results = []
        for face in target_faces:
            face_id = face["id"]
            crop_path = face["crop_path"]
            photo_id = face["photo_id"]

            age = await estimate_age(crop_path, user_dir)
            if age is not None:
                await conn.execute(
                    """INSERT INTO age_estimates (photo_id, face_id, estimated_age, method)
                       VALUES ($1, $2, $3, 'deepface')
                       ON CONFLICT (photo_id) DO UPDATE SET
                           face_id = $2, estimated_age = $3, method = 'deepface'""",
                    photo_id, face_id, age,
                )
                results.append({
                    "photo_id": photo_id,
                    "face_id": face_id,
                    "estimated_age": age,
                })

        return {"estimates": results, "count": len(results)}
