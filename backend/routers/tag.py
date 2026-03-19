from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from models.schema import get_db

router = APIRouter()


class TagRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2030)


@router.post("/{photo_id}/tag")
async def tag_photo(photo_id: str, body: TagRequest, request: Request):
    username = request.state.username
    """Assign a year to a photo."""
    db = await get_db(username)
    try:
        # Verify photo exists
        cursor = await db.execute("SELECT id FROM photos WHERE id = ?", (photo_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Photo not found")

        await db.execute(
            """INSERT OR REPLACE INTO tags (photo_id, year, tagged_at)
               VALUES (?, ?, datetime('now'))""",
            (photo_id, body.year),
        )
        await db.commit()

        return {"status": "tagged", "photo_id": photo_id, "year": body.year}
    finally:
        await db.close()


@router.delete("/{photo_id}/tag")
async def untag_photo(photo_id: str, request: Request):
    username = request.state.username
    """Remove year tag from a photo."""
    db = await get_db(username)
    try:
        await db.execute("DELETE FROM tags WHERE photo_id = ?", (photo_id,))
        await db.commit()
        return {"status": "untagged", "photo_id": photo_id}
    finally:
        await db.close()


@router.get("/target-photos")
async def get_target_photos(request: Request):
    username = request.state.username
    """Get all photos of the target person with tag status."""
    db = await get_db(username)
    try:
        cursor = await db.execute("""
            SELECT DISTINCT p.id, p.stored_filename, p.original_filename,
                   p.exif_date, p.width, p.height,
                   f.crop_path, f.confidence,
                   t.year as tagged_year
            FROM faces f
            JOIN photos p ON f.photo_id = p.id
            LEFT JOIN tags t ON p.id = t.photo_id
            WHERE f.is_target = 1
            ORDER BY t.year ASC NULLS LAST, p.uploaded_at ASC
        """)
        rows = await cursor.fetchall()

        photos = []
        for row in rows:
            photos.append({
                "id": row[0],
                "stored_filename": row[1],
                "original_filename": row[2],
                "exif_date": row[3],
                "width": row[4],
                "height": row[5],
                "face_crop_url": f"/data/{row[6]}",
                "confidence": row[7],
                "tagged_year": row[8],
                "url": f"/data/uploads/{row[1]}",
            })

        # Tag stats
        cursor2 = await db.execute("SELECT COUNT(*) FROM tags")
        tag_count = (await cursor2.fetchone())[0]

        return {
            "photos": photos,
            "total": len(photos),
            "tagged_count": tag_count,
            "min_required": 8,
            "recommended": 15,
        }
    finally:
        await db.close()
