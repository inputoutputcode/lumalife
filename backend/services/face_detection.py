import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

# Thread pool for CPU-bound DeepFace operations
_executor = ThreadPoolExecutor(max_workers=3)

# DeepFace lazy import to avoid slow startup
_deepface = None


def _get_deepface():
    global _deepface
    if _deepface is None:
        from deepface import DeepFace
        _deepface = DeepFace
    return _deepface


def _detect_faces_sync(image_path: str, user_dir: str) -> list[dict]:
    """Detect faces in image and return face data. Runs in thread pool."""
    DeepFace = _get_deepface()

    try:
        results = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend="retinaface",
            enforce_detection=False,
            align=True,
        )
    except Exception:
        return []

    faces = []
    for i, result in enumerate(results):
        if result.get("confidence", 0) < 0.1:
            continue

        # Skip tiny face crops (< 40px in either dimension)
        facial_area_check = result.get("facial_area", {})
        if facial_area_check.get("w", 0) < 40 or facial_area_check.get("h", 0) < 40:
            continue

        facial_area = result.get("facial_area", {})
        face_array = result.get("face")

        if face_array is None:
            continue

        # Save face crop
        face_id = str(uuid.uuid4())
        crop_filename = f"{face_id}.jpg"
        crop_path = os.path.join(user_dir, "processed", crop_filename)

        face_img = (np.array(face_array) * 255).astype(np.uint8)
        if face_img.ndim == 3 and face_img.shape[2] == 3:
            face_pil = Image.fromarray(face_img, "RGB")
        else:
            face_pil = Image.fromarray(face_img)
        face_pil.save(crop_path, "JPEG", quality=90)

        faces.append({
            "face_id": face_id,
            "crop_path": f"processed/{crop_filename}",
            "bbox": {
                "x": facial_area.get("x", 0),
                "y": facial_area.get("y", 0),
                "w": facial_area.get("w", 0),
                "h": facial_area.get("h", 0),
            },
            "confidence": result.get("confidence", 0),
        })

    return faces


def _extract_embedding_sync(image_path: str) -> list[float] | None:
    """Extract face embedding using ArcFace. Runs in thread pool."""
    DeepFace = _get_deepface()

    try:
        embeddings = DeepFace.represent(
            img_path=image_path,
            model_name="ArcFace",
            detector_backend="skip",
            enforce_detection=False,
        )
        if embeddings and len(embeddings) > 0:
            return embeddings[0].get("embedding", [])
    except Exception:
        pass
    return None


async def detect_faces(image_path: str, user_dir: str) -> list[dict]:
    """Async wrapper for face detection."""
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _detect_faces_sync, image_path, user_dir),
        timeout=120.0,
    )


async def extract_embedding(crop_path: str) -> list[float] | None:
    """Async wrapper for embedding extraction."""
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _extract_embedding_sync, crop_path),
        timeout=30.0,
    )


def _count_confident_faces(faces: list[dict], min_confidence: float = 0.5) -> int:
    """Count faces with real confidence (not fallback whole-image results)."""
    return sum(1 for f in faces if f.get("confidence", 0) >= min_confidence)


def _rotate_and_save(image_path: str, degrees_cw: int) -> None:
    """Rotate image on disk by degrees clockwise."""
    img = Image.open(image_path)
    rotated = img.rotate(-degrees_cw, expand=True)
    rotated.save(image_path, quality=95)


async def process_single_photo(photo_id: str, stored_filename: str, user_dir: str) -> list[dict]:
    """Detect faces and extract embeddings for a single photo.

    If no confident faces found, tries rotating 90°, 180°, 270° and keeps
    the rotation with the best face detection results (auto-rotation).
    The image file on disk is updated to the best rotation.
    """
    import shutil

    image_path = os.path.join(user_dir, "uploads", stored_filename)
    if not os.path.exists(image_path):
        return []

    loop = asyncio.get_event_loop()

    # Try original orientation first
    faces = await detect_faces(image_path, user_dir)
    best_confident = _count_confident_faces(faces)

    # If we found confident faces at 0°, skip rotation attempts
    if best_confident > 0:
        for face in faces:
            crop_full_path = os.path.join(user_dir, face["crop_path"])
            embedding = await extract_embedding(crop_full_path)
            face["embedding"] = embedding
        return faces

    # No confident faces — try 90° and 270° (most common rotation issues)
    best_faces = faces
    best_rotation = 0
    backup_path = image_path + ".bak"
    shutil.copy2(image_path, backup_path)

    try:
        for rotation in [90, 270]:
            shutil.copy2(backup_path, image_path)
            await loop.run_in_executor(_executor, _rotate_and_save, image_path, rotation)

            trial_faces = await detect_faces(image_path, user_dir)
            confident = _count_confident_faces(trial_faces)

            if confident > best_confident:
                best_faces = trial_faces
                best_rotation = rotation
                best_confident = confident
                break  # Found faces, no need to try more

        # Apply the winning rotation (or restore original)
        shutil.copy2(backup_path, image_path)
        if best_rotation > 0:
            await loop.run_in_executor(_executor, _rotate_and_save, image_path, best_rotation)
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)

    # Extract embeddings
    for face in best_faces:
        crop_full_path = os.path.join(user_dir, face["crop_path"])
        embedding = await extract_embedding(crop_full_path)
        face["embedding"] = embedding

    return best_faces
