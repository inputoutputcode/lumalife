import os
import shutil

from fastapi import APIRouter, Request

from models.schema import get_pool, get_user_dir

router = APIRouter()


@router.delete("/data/all")
async def delete_all_data(request: Request):
    """Delete all data for current user."""
    username = request.state.username
    user_id = request.state.user_id
    user_dir = get_user_dir(username)

    # Clear directories
    for subdir in ["uploads", "processed"]:
        dir_path = os.path.join(user_dir, subdir)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            os.makedirs(dir_path, exist_ok=True)

    # Delete user's data from shared DB (order matters for FK constraints)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM timeline_entries WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )
            await conn.execute(
                "DELETE FROM age_estimates WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )
            await conn.execute(
                "DELETE FROM tags WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )
            await conn.execute(
                "DELETE FROM faces WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )
            await conn.execute("DELETE FROM clusters WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM photos WHERE user_id = $1", user_id)

    return {"status": "deleted", "message": "All data has been deleted"}


@router.post("/data/reprocess")
async def reprocess(request: Request):
    """Reset processing state so photos can be re-processed."""
    username = request.state.username
    user_id = request.state.user_id
    user_dir = get_user_dir(username)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM timeline_entries WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )
            await conn.execute(
                "DELETE FROM age_estimates WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )
            await conn.execute(
                "DELETE FROM tags WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )
            await conn.execute(
                "DELETE FROM faces WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
                user_id,
            )
            await conn.execute("DELETE FROM clusters WHERE user_id = $1", user_id)
            await conn.execute(
                "UPDATE photos SET processed = FALSE WHERE user_id = $1", user_id
            )

    for subdir in ["processed"]:
        dir_path = os.path.join(user_dir, subdir)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            os.makedirs(dir_path, exist_ok=True)

    return {"status": "reset", "message": "Processing state reset. Run /api/photos/process to re-process."}


@router.get("/data/export")
async def export_timeline(request: Request):
    """Export timeline data as JSON."""
    user_id = request.state.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, original_filename, stored_filename, exif_date,
                      width, height, uploaded_at
               FROM photos WHERE user_id = $1 ORDER BY uploaded_at""",
            user_id,
        )
        photos = [
            {"id": r["id"], "original_filename": r["original_filename"],
             "stored_filename": r["stored_filename"], "exif_date": r["exif_date"],
             "width": r["width"], "height": r["height"],
             "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None}
            for r in rows
        ]

        rows = await conn.fetch(
            "SELECT t.photo_id, t.year FROM tags t JOIN photos p ON t.photo_id = p.id WHERE p.user_id = $1",
            user_id,
        )
        tags = [{"photo_id": r["photo_id"], "year": r["year"]} for r in rows]

        rows = await conn.fetch(
            """SELECT ae.photo_id, ae.estimated_age, ae.estimated_year, ae.method
               FROM age_estimates ae JOIN photos p ON ae.photo_id = p.id
               WHERE p.user_id = $1""",
            user_id,
        )
        ages = [
            {"photo_id": r["photo_id"], "estimated_age": r["estimated_age"],
             "estimated_year": r["estimated_year"], "method": r["method"]}
            for r in rows
        ]

        rows = await conn.fetch(
            """SELECT te.photo_id, te.estimated_year, te.era_label, te.era_start, te.era_end, te.sort_order
               FROM timeline_entries te JOIN photos p ON te.photo_id = p.id
               WHERE p.user_id = $1 ORDER BY te.sort_order""",
            user_id,
        )
        timeline = [
            {"photo_id": r["photo_id"], "estimated_year": r["estimated_year"],
             "era_label": r["era_label"], "era_start": r["era_start"],
             "era_end": r["era_end"], "sort_order": r["sort_order"]}
            for r in rows
        ]

        return {"version": "1.0", "photos": photos, "tags": tags,
                "age_estimates": ages, "timeline": timeline}


@router.get("/data/stats")
async def get_stats(request: Request):
    """Get current data statistics."""
    user_id = request.state.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        stats = {}
        stats["total_photos"] = await conn.fetchval(
            "SELECT COUNT(*) FROM photos WHERE user_id = $1", user_id
        )
        stats["total_faces"] = await conn.fetchval(
            "SELECT COUNT(*) FROM faces f JOIN photos p ON f.photo_id = p.id WHERE p.user_id = $1", user_id
        )
        stats["total_clusters"] = await conn.fetchval(
            "SELECT COUNT(*) FROM clusters WHERE user_id = $1", user_id
        )
        stats["tagged_photos"] = await conn.fetchval(
            "SELECT COUNT(*) FROM tags t JOIN photos p ON t.photo_id = p.id WHERE p.user_id = $1", user_id
        )
        stats["age_estimates"] = await conn.fetchval(
            "SELECT COUNT(*) FROM age_estimates ae JOIN photos p ON ae.photo_id = p.id WHERE p.user_id = $1",
            user_id,
        )
        stats["timeline_entries"] = await conn.fetchval(
            "SELECT COUNT(*) FROM timeline_entries te JOIN photos p ON te.photo_id = p.id WHERE p.user_id = $1",
            user_id,
        )
        stats["processed_photos"] = await conn.fetchval(
            "SELECT COUNT(*) FROM photos WHERE user_id = $1 AND processed = TRUE", user_id
        )
        stats["target_faces"] = await conn.fetchval(
            "SELECT COUNT(*) FROM faces f JOIN photos p ON f.photo_id = p.id WHERE p.user_id = $1 AND f.is_target = TRUE",
            user_id,
        )
        return stats
