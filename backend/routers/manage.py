import os
import shutil

from fastapi import APIRouter, Request

from models.schema import get_db, get_user_dir, get_db_path

router = APIRouter()


@router.delete("/data/all")
async def delete_all_data(request: Request):
    """Delete all data for current user."""
    username = request.state.username
    user_dir = get_user_dir(username)

    # Clear directories
    for subdir in ["uploads", "processed", "embeddings"]:
        dir_path = os.path.join(user_dir, subdir)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            os.makedirs(dir_path, exist_ok=True)

    # Drop and recreate DB
    db_path = get_db_path(username)
    for suffix in ["", "-wal", "-shm"]:
        p = db_path + suffix
        if os.path.exists(p):
            os.remove(p)

    # Re-init tables
    db = await get_db(username)
    await db.close()

    return {"status": "deleted", "message": "All data has been deleted"}


@router.post("/data/reprocess")
async def reprocess(request: Request):
    """Reset processing state so photos can be re-processed."""
    username = request.state.username
    user_dir = get_user_dir(username)
    db = await get_db(username)
    try:
        await db.execute("DELETE FROM timeline_entries")
        await db.execute("DELETE FROM age_estimates")
        await db.execute("DELETE FROM faces")
        await db.execute("DELETE FROM clusters")
        await db.execute("UPDATE photos SET processed = 0")
        await db.commit()

        for subdir in ["processed", "embeddings"]:
            dir_path = os.path.join(user_dir, subdir)
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
                os.makedirs(dir_path, exist_ok=True)

        return {"status": "reset", "message": "Processing state reset. Run /api/photos/process to re-process."}
    finally:
        await db.close()


@router.get("/data/export")
async def export_timeline(request: Request):
    """Export timeline data as JSON."""
    username = request.state.username
    db = await get_db(username)
    try:
        cursor = await db.execute(
            """SELECT p.id, p.original_filename, p.stored_filename, p.exif_date,
                      p.width, p.height, p.uploaded_at
               FROM photos p ORDER BY p.uploaded_at"""
        )
        photos = [
            {"id": r[0], "original_filename": r[1], "stored_filename": r[2],
             "exif_date": r[3], "width": r[4], "height": r[5], "uploaded_at": r[6]}
            for r in await cursor.fetchall()
        ]

        cursor = await db.execute("SELECT photo_id, year FROM tags")
        tags = [{"photo_id": r[0], "year": r[1]} for r in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT photo_id, estimated_age, estimated_year, method FROM age_estimates"
        )
        ages = [
            {"photo_id": r[0], "estimated_age": r[1], "estimated_year": r[2], "method": r[3]}
            for r in await cursor.fetchall()
        ]

        cursor = await db.execute(
            "SELECT photo_id, estimated_year, era_label, era_start, era_end, sort_order FROM timeline_entries ORDER BY sort_order"
        )
        timeline = [
            {"photo_id": r[0], "estimated_year": r[1], "era_label": r[2],
             "era_start": r[3], "era_end": r[4], "sort_order": r[5]}
            for r in await cursor.fetchall()
        ]

        return {"version": "1.0", "photos": photos, "tags": tags,
                "age_estimates": ages, "timeline": timeline}
    finally:
        await db.close()


@router.get("/data/stats")
async def get_stats(request: Request):
    """Get current data statistics."""
    username = request.state.username
    db = await get_db(username)
    try:
        stats = {}
        for table, key in [
            ("photos", "total_photos"),
            ("faces", "total_faces"),
            ("clusters", "total_clusters"),
            ("tags", "tagged_photos"),
            ("age_estimates", "age_estimates"),
            ("timeline_entries", "timeline_entries"),
        ]:
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
            stats[key] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM photos WHERE processed = 1")
        stats["processed_photos"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM faces WHERE is_target = 1")
        stats["target_faces"] = (await cursor.fetchone())[0]

        return stats
    finally:
        await db.close()
