import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

_executor = ThreadPoolExecutor(max_workers=2)

# InsightFace model (lazy loaded)
_insightface_app = None


def _get_insightface():
    global _insightface_app
    if _insightface_app is not None:
        return _insightface_app

    import insightface
    _insightface_app = insightface.app.FaceAnalysis(
        name="buffalo_l",
        providers=["CPUExecutionProvider"],
    )
    # det_size controls detection input size — larger = better for small faces
    _insightface_app.prepare(ctx_id=0, det_size=(640, 640))
    print("InsightFace buffalo_l model loaded")
    return _insightface_app


def _detect_faces_insightface(image_path: str, user_dir: str) -> list[dict]:
    """Detect faces using InsightFace (SCRFD + ArcFace + age/gender in one pass)."""
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        return []

    app = _get_insightface()
    faces_result = app.get(img)

    faces = []
    for face in faces_result:
        bbox = face.bbox.astype(int)
        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
        w, h = x2 - x1, y2 - y1

        # Skip tiny faces
        if w < 40 or h < 40:
            continue

        # Skip low confidence
        det_score = float(face.det_score) if hasattr(face, 'det_score') else 0
        if det_score < 0.3:
            continue

        face_id = str(uuid.uuid4())
        crop_filename = f"{face_id}.jpg"
        crop_path = os.path.join(user_dir, "processed", crop_filename)

        # Crop face with padding
        img_h, img_w = img.shape[:2]
        pad_x, pad_y = int(w * 0.2), int(h * 0.2)
        cx1 = max(0, x1 - pad_x)
        cy1 = max(0, y1 - pad_y)
        cx2 = min(img_w, x2 + pad_x)
        cy2 = min(img_h, y2 + pad_y)
        crop = img[cy1:cy2, cx1:cx2]
        cv2.imwrite(crop_path, crop, [cv2.IMWRITE_JPEG_QUALITY, 90])

        # Get embedding (512-dim from ArcFace)
        embedding = face.embedding.tolist() if face.embedding is not None else None

        # Get age and gender
        age = int(face.age) if hasattr(face, 'age') and face.age is not None else None
        gender = "male" if hasattr(face, 'gender') and face.gender == 1 else "female" if hasattr(face, 'gender') and face.gender == 0 else None

        # Get landmarks
        landmarks = None
        if hasattr(face, 'kps') and face.kps is not None:
            kps = face.kps
            if len(kps) >= 5:
                landmarks = {
                    "right_eye": [float(kps[0][0]), float(kps[0][1])],
                    "left_eye": [float(kps[1][0]), float(kps[1][1])],
                    "nose": [float(kps[2][0]), float(kps[2][1])],
                    "mouth_right": [float(kps[3][0]), float(kps[3][1])],
                    "mouth_left": [float(kps[4][0]), float(kps[4][1])],
                }

        faces.append({
            "face_id": face_id,
            "crop_path": f"processed/{crop_filename}",
            "bbox": {"x": int(x1), "y": int(y1), "w": int(w), "h": int(h)},
            "confidence": det_score,
            "embedding": embedding,
            "landmarks": landmarks,
            "estimated_age": age,
            "gender": gender,
        })

    return faces


async def detect_faces(image_path: str, user_dir: str) -> list[dict]:
    """Detect faces using InsightFace (SCRFD detector + ArcFace embedding + age/gender)."""
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _detect_faces_insightface, image_path, user_dir),
        timeout=300.0,
    )


async def extract_embedding(crop_path: str) -> list[float] | None:
    """Extract embedding from a face crop — not needed with InsightFace (already extracted)."""
    # InsightFace returns embedding during detection, so this is only for backward compat
    return None


def _count_confident_faces(faces: list[dict], min_confidence: float = 0.5) -> int:
    return sum(1 for f in faces if f.get("confidence", 0) >= min_confidence)


def _rotate_and_save(image_path: str, degrees_cw: int) -> None:
    img = Image.open(image_path)
    rotated = img.rotate(-degrees_cw, expand=True)
    rotated.save(image_path, quality=95)


async def process_single_photo(photo_id: str, stored_filename: str, user_dir: str) -> list[dict]:
    """Detect faces, extract embeddings, and estimate age in one pass with InsightFace."""
    import shutil

    image_path = os.path.join(user_dir, "uploads", stored_filename)
    if not os.path.exists(image_path):
        return []

    loop = asyncio.get_event_loop()

    # Try original orientation
    faces = await detect_faces(image_path, user_dir)
    best_confident = _count_confident_faces(faces)

    if best_confident > 0:
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

    return best_faces
