import os
import uuid
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Request

from models.schema import get_db, get_user_dir
from utils.validation import validate_mime_type, validate_file_size, MAX_FILES, MAX_FILE_SIZE
from utils.exif import extract_exif, strip_exif

router = APIRouter()


@router.post("/upload")
async def upload_photos(request: Request, files: list[UploadFile] = File(...)):
    username = request.state.username
    user_dir = get_user_dir(username)
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES} files allowed per upload",
        )

    db = await get_db(username)
    try:
        # Check existing count
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM photos")
        row = await cursor.fetchone()
        existing_count = row[0] if row else 0

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

                # Store metadata in SQLite
                await db.execute(
                    """INSERT INTO photos (id, original_filename, stored_filename, mime_type,
                       file_size, width, height, exif_date, orientation, uploaded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        photo_id,
                        file.filename,
                        stored_filename,
                        mime_type,
                        len(clean_content),
                        exif_data.get("width"),
                        exif_data.get("height"),
                        exif_data.get("date"),
                        exif_data.get("orientation", 1),
                        datetime.now().isoformat(),
                    ),
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

        await db.commit()

        return {
            "uploaded": len(results),
            "errors": len(errors),
            "photos": results,
            "error_details": errors,
        }
    finally:
        await db.close()


@router.get("/list")
async def list_photos(request: Request):
    username = request.state.username
    db = await get_db(username)
    try:
        cursor = await db.execute(
            "SELECT id, original_filename, stored_filename, mime_type, file_size, "
            "width, height, exif_date, uploaded_at, processed FROM photos ORDER BY uploaded_at DESC"
        )
        rows = await cursor.fetchall()
        photos = []
        for row in rows:
            photos.append({
                "id": row[0],
                "original_filename": row[1],
                "stored_filename": row[2],
                "mime_type": row[3],
                "file_size": row[4],
                "width": row[5],
                "height": row[6],
                "exif_date": row[7],
                "uploaded_at": row[8],
                "processed": bool(row[9]),
                "url": f"/data/uploads/{row[2]}",
            })
        return {"photos": photos, "count": len(photos)}
    finally:
        await db.close()
