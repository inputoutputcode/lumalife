import os
import uuid
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor

import httpx
import numpy as np
from PIL import Image

MIVOLO_URL = os.environ.get("MIVOLO_URL", "http://mivolo:8010")

# Thread pool for CPU-bound DeepFace embedding extraction
_executor = ThreadPoolExecutor(max_workers=3)

_deepface = None


def _get_deepface():
    global _deepface
    if _deepface is None:
        from deepface import DeepFace
        _deepface = DeepFace
    return _deepface


async def _detect_faces_mivolo(image_path: str, user_dir: str) -> list[dict]:
    """Detect faces using MiVOLO (GPU-accelerated YOLOv8 + age/gender)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(image_path, "rb") as f:
            resp = await client.post(
                f"{MIVOLO_URL}/detect",
                files={"file": ("photo.jpg", f, "image/jpeg")},
            )
        if resp.status_code != 200:
            raise Exception(f"MiVOLO detect failed: {resp.status_code} {resp.text}")

        data = resp.json()

    faces = []
    for face_data in data.get("faces", []):
        bbox = face_data["bbox"]

        # Skip tiny faces
        if bbox["w"] < 40 or bbox["h"] < 40:
            continue

        # Decode crop from base64
        face_id = str(uuid.uuid4())
        crop_filename = f"{face_id}.jpg"
        crop_path = os.path.join(user_dir, "processed", crop_filename)

        crop_bytes = base64.b64decode(face_data["crop_b64"])
        with open(crop_path, "wb") as f:
            f.write(crop_bytes)

        faces.append({
            "face_id": face_id,
            "crop_path": f"processed/{crop_filename}",
            "bbox": bbox,
            "confidence": face_data.get("confidence", 0),
            "landmarks": None,  # YOLOv8 doesn't return landmarks
            "estimated_age": face_data.get("age"),
            "gender": face_data.get("gender"),
        })

    return faces


def _detect_faces_deepface(image_path: str, user_dir: str) -> list[dict]:
    """Fallback: detect faces using DeepFace/SSD (CPU)."""
    DeepFace = _get_deepface()

    try:
        results = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend="ssd",  # SSD is faster than RetinaFace on ARM CPU
            enforce_detection=False,
            align=True,
        )
    except Exception:
        return []

    faces = []
    for result in results:
        if result.get("confidence", 0) < 0.1:
            continue

        facial_area = result.get("facial_area", {})
        if facial_area.get("w", 0) < 40 or facial_area.get("h", 0) < 40:
            continue

        face_array = result.get("face")
        if face_array is None:
            continue

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
            "landmarks": None,
        })

    return faces


async def detect_faces(image_path: str, user_dir: str) -> list[dict]:
    """Detect faces — MiVOLO (GPU) first, fallback to DeepFace/SSD (CPU)."""
    try:
        return await _detect_faces_mivolo(image_path, user_dir)
    except Exception as e:
        print(f"MiVOLO detection failed, falling back to DeepFace: {e}")
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(_executor, _detect_faces_deepface, image_path, user_dir),
            timeout=120.0,
        )


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


async def extract_embedding(crop_path: str) -> list[float] | None:
    """Async wrapper for embedding extraction."""
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _extract_embedding_sync, crop_path),
        timeout=60.0,
    )


def _count_confident_faces(faces: list[dict], min_confidence: float = 0.5) -> int:
    return sum(1 for f in faces if f.get("confidence", 0) >= min_confidence)


def _rotate_and_save(image_path: str, degrees_cw: int) -> None:
    img = Image.open(image_path)
    rotated = img.rotate(-degrees_cw, expand=True)
    rotated.save(image_path, quality=95)


async def process_single_photo(photo_id: str, stored_filename: str, user_dir: str) -> list[dict]:
    """Detect faces and extract embeddings for a single photo."""
    import shutil

    image_path = os.path.join(user_dir, "uploads", stored_filename)
    if not os.path.exists(image_path):
        return []

    loop = asyncio.get_event_loop()

    # Try original orientation
    faces = await detect_faces(image_path, user_dir)
    best_confident = _count_confident_faces(faces)

    if best_confident > 0:
        for face in faces:
            crop_full_path = os.path.join(user_dir, face["crop_path"])
            embedding = await extract_embedding(crop_full_path)
            face["embedding"] = embedding
        return faces

    # No confident faces — try 90° and 270°
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
                break

        shutil.copy2(backup_path, image_path)
        if best_rotation > 0:
            await loop.run_in_executor(_executor, _rotate_and_save, image_path, best_rotation)
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)

    for face in best_faces:
        crop_full_path = os.path.join(user_dir, face["crop_path"])
        embedding = await extract_embedding(crop_full_path)
        face["embedding"] = embedding

    return best_faces
