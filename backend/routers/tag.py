from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from models.schema import get_pool

router = APIRouter()


class TagRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2030)
    month: int | None = Field(None, ge=1, le=12)


@router.post("/{photo_id}/tag")
async def tag_photo(photo_id: str, body: TagRequest, request: Request):
    """Assign a year to a photo."""
    user_id = request.state.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify photo exists and belongs to user
        row = await conn.fetchrow(
            "SELECT id FROM photos WHERE id = $1 AND user_id = $2", photo_id, user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Photo not found")

        await conn.execute(
            """INSERT INTO tags (photo_id, year, month)
               VALUES ($1, $2, $3)
               ON CONFLICT (photo_id) DO UPDATE SET year = $2, month = $3, tagged_at = NOW()""",
            photo_id, body.year, body.month,
        )

        return {"status": "tagged", "photo_id": photo_id, "year": body.year, "month": body.month}


@router.delete("/{photo_id}/tag")
async def untag_photo(photo_id: str, request: Request):
    """Remove year tag from a photo."""
    user_id = request.state.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM tags WHERE photo_id = $1 AND photo_id IN (SELECT id FROM photos WHERE user_id = $2)",
            photo_id, user_id,
        )
        return {"status": "untagged", "photo_id": photo_id}


@router.get("/target-photos")
async def get_target_photos(request: Request):
    """Get all user photos with tag status. Shows all photos, not just faces."""
    user_id = request.state.user_id
    username = request.state.username
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.id, p.stored_filename, p.original_filename,
                   p.exif_date, p.width, p.height, p.uploaded_at,
                   t.year as tagged_year, t.month as tagged_month,
                   ae.estimated_age
            FROM photos p
            LEFT JOIN tags t ON p.id = t.photo_id
            LEFT JOIN age_estimates ae ON p.id = ae.photo_id
            WHERE p.user_id = $1
            ORDER BY t.year ASC NULLS LAST, p.uploaded_at ASC
        """, user_id)

        photos = []
        for row in rows:
            estimated_year = None
            if row["estimated_age"] is not None:
                # Show estimated year range based on age estimate (±4 years)
                estimated_year = row["estimated_age"]

            photos.append({
                "id": row["id"],
                "stored_filename": row["stored_filename"],
                "original_filename": row["original_filename"],
                "exif_date": row["exif_date"],
                "width": row["width"],
                "height": row["height"],
                "tagged_year": row["tagged_year"],
                "tagged_month": row["tagged_month"],
                "estimated_age": float(row["estimated_age"]) if row["estimated_age"] is not None else None,
                "url": f"/data/{username}/uploads/{row['stored_filename']}",
            })

        tag_count = await conn.fetchval(
            "SELECT COUNT(*) FROM tags t JOIN photos p ON t.photo_id = p.id WHERE p.user_id = $1",
            user_id,
        )

        return {
            "photos": photos,
            "total": len(photos),
            "tagged_count": tag_count,
            "min_required": 3,
            "recommended": 10,
        }
