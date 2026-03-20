import os
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from pydantic import BaseModel, Field

from models.schema import get_pool, get_user_dir
from utils.validation import validate_mime_type, validate_file_size, MAX_FILES, MAX_FILE_SIZE
from utils.exif import extract_exif, strip_exif

router = APIRouter()


@router.post("/upload")
async def upload_photos(request: Request, files: list[UploadFile] = File(...)):
    username = request.state.username
    user_id = request.state.user_id
    user_dir = get_user_dir(username)
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES} files allowed per upload",
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check existing count
        existing_count = await conn.fetchval(
            "SELECT COUNT(*) FROM photos WHERE user_id = $1", user_id
        )

        if existing_count + len(files) > MAX_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Upload would exceed {MAX_FILES} photo limit. Currently have {existing_count} photos.",
            )

        results = []
        errors = []

        for file in files:
            try:
                content = await file.read()

                # Duplicate detection (same filename + same size)
                existing = await conn.fetchval(
                    "SELECT id FROM photos WHERE user_id = $1 AND original_filename = $2 AND file_size = $3",
                    user_id, file.filename, len(content),
                )
                if existing:
                    errors.append({
                        "filename": file.filename,
                        "error": "Duplicate photo (already uploaded)",
                    })
                    continue

                if not validate_file_size(len(content)):
                    errors.append({
                        "filename": file.filename,
                        "error": f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit",
                    })
                    continue

                mime_type = validate_mime_type(content, file.content_type or "")
                if not mime_type:
                    errors.append({
                        "filename": file.filename,
                        "error": "Invalid image format. Allowed: JPEG, PNG, WebP, HEIC",
                    })
                    continue

                # Extract EXIF before stripping
                exif_data = extract_exif(content)

                # Strip EXIF (keep orientation applied)
                clean_content = strip_exif(content)

                # Generate UUID filename
                photo_id = str(uuid.uuid4())
                ext_map = {
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/webp": ".webp",
                    "image/heic": ".heic",
                    "image/heif": ".heif",
                }
                ext = ext_map.get(mime_type, ".jpg")
                stored_filename = f"{photo_id}{ext}"

                # Save to user's uploads directory
                upload_path = os.path.join(user_dir, "uploads", stored_filename)
                with open(upload_path, "wb") as f:
                    f.write(clean_content)

                # Store metadata in PostgreSQL
                await conn.execute(
                    """INSERT INTO photos (id, user_id, original_filename, stored_filename,
                       mime_type, file_size, width, height, exif_date, orientation)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                    photo_id, user_id, file.filename, stored_filename,
                    mime_type, len(clean_content),
                    exif_data.get("width"), exif_data.get("height"),
                    exif_data.get("date"), exif_data.get("orientation", 1),
                )

                results.append({
                    "id": photo_id,
                    "filename": stored_filename,
                    "original_filename": file.filename,
                    "mime_type": mime_type,
                    "size": len(clean_content),
                    "width": exif_data.get("width"),
                    "height": exif_data.get("height"),
                    "exif_date": exif_data.get("date"),
                    "orientation": exif_data.get("orientation", 1),
                    "orientation_label": exif_data.get("orientation_label", "Normal"),
                    "had_exif": exif_data.get("had_exif", False),
                })

            except HTTPException:
                raise
            except Exception as e:
                errors.append({
                    "filename": file.filename or "unknown",
                    "error": str(e),
                })

        return {
            "uploaded": len(results),
            "errors": len(errors),
            "photos": results,
            "error_details": errors,
        }


@router.post("/{photo_id}/rotate")
async def rotate_photo(photo_id: str, request: Request):
    """Rotate a photo 90° clockwise. Can be called multiple times."""
    user_id = request.state.user_id
    username = request.state.username
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stored_filename, width, height FROM photos WHERE id = $1 AND user_id = $2",
            photo_id, user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Photo not found")

        user_dir = get_user_dir(username)
        file_path = os.path.join(user_dir, "uploads", row["stored_filename"])

        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="Photo file not found")

        # Rotate 90° counter-clockwise
        from PIL import Image
        img = Image.open(file_path)
        rotated = img.rotate(90, expand=True)
        rotated.save(file_path, quality=95)

        new_width, new_height = rotated.size

        await conn.execute(
            "UPDATE photos SET width = $1, height = $2 WHERE id = $3",
            new_width, new_height, photo_id,
        )

        return {
            "status": "rotated",
            "photo_id": photo_id,
            "width": new_width,
            "height": new_height,
            "url": f"/data/{username}/uploads/{row['stored_filename']}",
        }


@router.delete("/{photo_id}")
async def delete_photo(photo_id: str, request: Request):
    """Delete a single photo and its associated data."""
    user_id = request.state.user_id
    username = request.state.username
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stored_filename FROM photos WHERE id = $1 AND user_id = $2",
            photo_id, user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Photo not found")

        user_dir = get_user_dir(username)
        
        # Delete face crops
        face_rows = await conn.fetch(
            "SELECT crop_path FROM faces WHERE photo_id = $1", photo_id
        )
        for face_row in face_rows:
            crop_full = os.path.join(user_dir, face_row["crop_path"])
            if os.path.exists(crop_full):
                os.remove(crop_full)

        # Delete the photo file
        file_path = os.path.join(user_dir, "uploads", row["stored_filename"])
        if os.path.exists(file_path):
            os.remove(file_path)

        # Delete from DB (cascades to faces, tags, timeline_entries, age_estimates)
        await conn.execute("DELETE FROM photos WHERE id = $1", photo_id)

        return {"status": "deleted", "photo_id": photo_id}


@router.get("/profile")
async def get_profile(request: Request):
    """Get user profile (birth year, etc.)."""
    user_id = request.state.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT birth_year FROM users WHERE id = $1", user_id)
        return {"birth_year": row["birth_year"] if row else None}


class ProfileUpdate(BaseModel):
    birth_year: int = Field(..., ge=1900, le=2025)


@router.put("/profile")
async def update_profile(request: Request, body: ProfileUpdate):
    """Set user birth year."""
    user_id = request.state.user_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET birth_year = $1 WHERE id = $2", body.birth_year, user_id)
        return {"status": "updated", "birth_year": body.birth_year}


@router.get("/list")
async def list_photos(request: Request):
    user_id = request.state.user_id
    username = request.state.username
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, original_filename, stored_filename, mime_type, file_size,
                      width, height, exif_date, uploaded_at, processed
               FROM photos WHERE user_id = $1 ORDER BY uploaded_at DESC""",
            user_id,
        )
        photos = []
        for row in rows:
            photos.append({
                "id": row["id"],
                "original_filename": row["original_filename"],
                "stored_filename": row["stored_filename"],
                "mime_type": row["mime_type"],
                "file_size": row["file_size"],
                "width": row["width"],
                "height": row["height"],
                "exif_date": row["exif_date"],
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "processed": row["processed"],
                "url": f"/data/{username}/uploads/{row['stored_filename']}",
            })
        return {"photos": photos, "count": len(photos)}
