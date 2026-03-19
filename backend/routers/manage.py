import os
import shutil
import json

from fastapi import APIRouter

from models.schema import get_db, init_db, DB_PATH

router = APIRouter()

DATA_DIR = os.environ.get("DATA_DIR", "/data")


@router.delete("/data/all")
async def delete_all_data():
    """Delete all data — uploads, embeddings, DB."""
    # Clear directories
    for subdir in ["uploads", "processed", "embeddings"]:
        dir_path = os.path.join(DATA_DIR, subdir)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            os.makedirs(dir_path, exist_ok=True)

    # Drop and recreate DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    # Also remove WAL files
    for suffix in ["-wal", "-shm"]:
        wal_path = DB_PATH + suffix
        if os.path.exists(wal_path):
            os.remove(wal_path)

    await init_db()

    return {"status": "deleted", "message": "All data has been deleted"}


@router.post("/data/reprocess")
async def reprocess():
    """Reset processing state so photos can be re-processed."""
    db = await get_db()
    try:
        # Clear processing artifacts but keep photos and tags
        await db.execute("DELETE FROM timeline_entries")
        await db.execute("DELETE FROM age_estimates")
        await db.execute("DELETE FROM faces")
        await db.execute("DELETE FROM clusters")
        await db.execute("UPDATE photos SET processed = 0")
        await db.commit()

        # Clear processed face crops and embeddings
        for subdir in ["processed", "embeddings"]:
            dir_path = os.path.join(DATA_DIR, subdir)
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
                os.makedirs(dir_path, exist_ok=True)

        return {"status": "reset", "message": "Processing state reset. Run /api/photos/process to re-process."}
    finally:
        await db.close()


@router.get("/data/export")
async def export_timeline():
    """Export timeline data as JSON."""
    db = await get_db()
    try:
        # Photos
        cursor = await db.execute(
            """SELECT p.id, p.original_filename, p.stored_filename, p.exif_date,
                      p.width, p.height, p.uploaded_at
               FROM photos p ORDER BY p.uploaded_at"""
        )
        photos = []
        for row in await cursor.fetchall():
            photos.append({
                "id": row[0],
                "original_filename": row[1],
                "stored_filename": row[2],
                "exif_date": row[3],
                "width": row[4],
                "height": row[5],
                "uploaded_at": row[6],
            })

        # Tags
        cursor = await db.execute("SELECT photo_id, year FROM tags")
        tags = [{"photo_id": r[0], "year": r[1]} for r in await cursor.fetchall()]

        # Age estimates
        cursor = await db.execute(
            "SELECT photo_id, estimated_age, estimated_year, method FROM age_estimates"
        )
        ages = [
            {"photo_id": r[0], "estimated_age": r[1], "estimated_year": r[2], "method": r[3]}
            for r in await cursor.fetchall()
        ]

        # Timeline entries
        cursor = await db.execute(
            "SELECT photo_id, estimated_year, era_label, era_start, era_end, sort_order FROM timeline_entries ORDER BY sort_order"
        )
        timeline = [
            {
                "photo_id": r[0],
                "estimated_year": r[1],
                "era_label": r[2],
                "era_start": r[3],
                "era_end": r[4],
                "sort_order": r[5],
            }
            for r in await cursor.fetchall()
        ]

        return {
            "version": "1.0",
            "photos": photos,
            "tags": tags,
            "age_estimates": ages,
            "timeline": timeline,
        }
    finally:
        await db.close()


@router.get("/data/stats")
async def get_stats():
    """Get current data statistics."""
    db = await get_db()
    try:
        stats = {}

        cursor = await db.execute("SELECT COUNT(*) FROM photos")
        stats["total_photos"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM photos WHERE processed = 1")
        stats["processed_photos"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM faces")
        stats["total_faces"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM faces WHERE is_target = 1")
        stats["target_faces"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM clusters")
        stats["total_clusters"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM tags")
        stats["tagged_photos"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM age_estimates")
        stats["age_estimates"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM timeline_entries")
        stats["timeline_entries"] = (await cursor.fetchone())[0]

        return stats
    finally:
        await db.close()
