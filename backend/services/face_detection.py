import os
import uuid
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

DATA_DIR = os.environ.get("DATA_DIR", "/data")

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


def _detect_faces_sync(image_path: str) -> list[dict]:
    """Detect faces in image and return face data. Runs in thread pool."""
    DeepFace = _get_deepface()

    try:
        results = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend="ssd",
            enforce_detection=False,
            align=True,
        )
    except Exception:
        return []

    faces = []
    for i, result in enumerate(results):
        if result.get("confidence", 0) < 0.1:
            continue

        facial_area = result.get("facial_area", {})
        face_array = result.get("face")

        if face_array is None:
            continue

        # Save face crop
        face_id = str(uuid.uuid4())
        crop_filename = f"{face_id}.jpg"
        crop_path = os.path.join(DATA_DIR, "processed", crop_filename)

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


async def detect_faces(image_path: str) -> list[dict]:
    """Async wrapper for face detection."""
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _detect_faces_sync, image_path),
        timeout=30.0,
    )


async def extract_embedding(crop_path: str) -> list[float] | None:
    """Async wrapper for embedding extraction."""
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _extract_embedding_sync, crop_path),
        timeout=30.0,
    )


async def process_single_photo(photo_id: str, stored_filename: str) -> list[dict]:
    """Detect faces and extract embeddings for a single photo."""
    image_path = os.path.join(DATA_DIR, "uploads", stored_filename)

    if not os.path.exists(image_path):
        return []

    faces = await detect_faces(image_path)

    for face in faces:
        crop_full_path = os.path.join(DATA_DIR, face["crop_path"])
        embedding = await extract_embedding(crop_full_path)

        if embedding is not None:
            embedding_filename = f"{face['face_id']}.json"
            embedding_path = os.path.join(DATA_DIR, "embeddings", embedding_filename)
            with open(embedding_path, "w") as f:
                json.dump(embedding, f)
            face["embedding_path"] = f"embeddings/{embedding_filename}"
            face["embedding"] = embedding
        else:
            face["embedding_path"] = ""
            face["embedding"] = None

    return faces
