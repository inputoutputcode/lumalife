"""
MiVOLO Age & Gender Estimation API
Standalone microservice with GPU support.

Endpoints:
  POST /analyze       — upload a full image, get detected faces with age/gender
  POST /analyze-crop  — upload a pre-cropped face, get age/gender
  GET  /health        — health check
"""
import os
import io
import tempfile
from dataclasses import dataclass

import cv2
import numpy as np
import torch

# Patch torch.load for ultralytics compatibility (PyTorch 2.6+ defaults to weights_only=True)
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="MiVOLO Age Estimation", version="1.0")

# Lazy-loaded models
_predictor = None


@dataclass
class MiVOLOConfig:
    detector_weights: str = "/app/models/yolov8x_person_face.pt"
    checkpoint: str = "/app/models/mivolo_imdb.pth.tar"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    with_persons: bool = True
    disable_faces: bool = False
    draw: bool = False


def _get_predictor():
    global _predictor
    if _predictor is not None:
        return _predictor

    from mivolo.predictor import Predictor
    config = MiVOLOConfig()
    _predictor = Predictor(config, verbose=False)

    # Set confidence threshold — 0.45 catches real faces, filtering by size handles noise
    _predictor.detector.detector_kwargs["conf"] = 0.45

    return _predictor


def _pil_to_cv2(img: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR array."""
    rgb = np.array(img)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


@app.get("/health")
async def health():
    return {"status": "ok", "model": "MiVOLO", "gpu": torch.cuda.is_available()}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """Analyze a full image for faces with age and gender."""
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    try:
        predictor = _get_predictor()
        cv2_img = _pil_to_cv2(img)
        detected_objects, _ = predictor.recognize(cv2_img)

        results = []
        face_inds = detected_objects.get_bboxes_inds("face")
        for ind in face_inds:
            bbox = detected_objects.yolo_results.boxes[ind].xyxy[0].cpu().numpy()
            age = detected_objects.ages[ind]
            gender = detected_objects.genders[ind]
            conf = float(detected_objects.yolo_results.boxes[ind].conf[0])

            results.append({
                "age": round(float(age), 1) if age is not None else None,
                "gender": gender,
                "bbox": {
                    "x": int(bbox[0]),
                    "y": int(bbox[1]),
                    "w": int(bbox[2] - bbox[0]),
                    "h": int(bbox[3] - bbox[1]),
                },
                "confidence": round(conf, 4),
            })

        return {"faces": results, "count": len(results)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@app.post("/detect")
async def detect(file: UploadFile = File(...)):
    """Detect faces in an image. Returns bounding boxes only (for external embedding)."""
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    try:
        predictor = _get_predictor()
        cv2_img = _pil_to_cv2(img)
        try:
            detected_objects, _ = predictor.recognize(cv2_img)
        except Exception as e:
            # Some images cause numeric errors in YOLOv8 — return empty
            print(f"Detection error (returning empty): {e}")
            return {"faces": [], "count": 0}

        results = []
        face_inds = detected_objects.get_bboxes_inds("face")
        for ind in face_inds:
            conf = float(detected_objects.yolo_results.boxes[ind].conf[0])
            bbox = detected_objects.yolo_results.boxes[ind].xyxy[0].cpu().numpy()

            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            w, h = x2 - x1, y2 - y1

            # Filter: minimum face size (60px in both dimensions)
            if w < 60 or h < 60:
                continue

            # Filter: aspect ratio sanity (faces are roughly square, allow 1:3 ratio)
            aspect = max(w, h) / max(min(w, h), 1)
            if aspect > 3.0:
                continue

            # Filter: face area must be at least 0.1% of image area
            img_w, img_h = img.size
            face_area_pct = (w * h) / (img_w * img_h) * 100
            if face_area_pct < 0.1:
                continue

            age = detected_objects.ages[ind]
            gender = detected_objects.genders[ind]

            # Expand bbox by 20% for better face crops
            w, h = x2 - x1, y2 - y1
            pad_x, pad_y = int(w * 0.2), int(h * 0.2)
            img_w, img_h = img.size
            cx1 = max(0, x1 - pad_x)
            cy1 = max(0, y1 - pad_y)
            cx2 = min(img_w, x2 + pad_x)
            cy2 = min(img_h, y2 + pad_y)

            # Crop and encode as base64
            crop = img.crop((cx1, cy1, cx2, cy2))
            buf = io.BytesIO()
            crop.save(buf, format="JPEG", quality=90)
            import base64
            crop_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            results.append({
                "bbox": {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1},
                "crop_bbox": {"x": cx1, "y": cy1, "w": cx2 - cx1, "h": cy2 - cy1},
                "confidence": round(conf, 4),
                "age": round(float(age), 1) if age is not None else None,
                "gender": gender,
                "crop_b64": crop_b64,
            })

        # Sort by confidence, keep top 10 max
        results.sort(key=lambda f: f["confidence"], reverse=True)
        results = results[:10]

        # Noise detection: if 5+ faces found and best conf < 0.8, likely scan artifacts
        if len(results) >= 5 and results[0]["confidence"] < 0.8:
            results = []

        return {"faces": results, "count": len(results)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}")


@app.post("/analyze-crop")
async def analyze_crop(file: UploadFile = File(...)):
    """Analyze a pre-cropped face for age and gender."""
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    try:
        predictor = _get_predictor()
        cv2_img = _pil_to_cv2(img)

        try:
            detected_objects, _ = predictor.recognize(cv2_img)
        except Exception:
            return {"age": None, "gender": None, "note": "Detection error"}

        face_inds = detected_objects.get_bboxes_inds("face")
        if face_inds:
            ind = face_inds[0]
            return {
                "age": round(float(detected_objects.ages[ind]), 1) if detected_objects.ages[ind] is not None else None,
                "gender": detected_objects.genders[ind],
            }

        person_inds = detected_objects.get_bboxes_inds("person")
        if person_inds:
            ind = person_inds[0]
            return {
                "age": round(float(detected_objects.ages[ind]), 1) if detected_objects.ages[ind] is not None else None,
                "gender": detected_objects.genders[ind],
            }

        return {"age": None, "gender": None, "note": "No face or person detected in crop"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


from fastapi import Form

@app.post("/analyze-with-bbox")
async def analyze_with_bbox(
    file: UploadFile = File(...),
    x: int = Form(0), y: int = Form(0), w: int = Form(0), h: int = Form(0)
):
    """Analyze a full image with a known face bounding box.
    
    Uses a lower confidence threshold since we already know where the face is.
    """
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    try:
        predictor = _get_predictor()
        
        # Temporarily lower threshold for bbox-guided detection
        original_conf = predictor.detector.detector_kwargs["conf"]
        predictor.detector.detector_kwargs["conf"] = 0.2
        
        cv2_img = _pil_to_cv2(img)

        try:
            detected_objects, _ = predictor.recognize(cv2_img)
        except Exception:
            return {"age": None, "gender": None, "note": "Detection error"}
        finally:
            predictor.detector.detector_kwargs["conf"] = original_conf

        # Debug: uncomment to see what MiVOLO finds
        # print(f"analyze-with-bbox: {detected_objects.n_faces} faces, {detected_objects.n_persons} persons")

        # Find the MiVOLO detection closest to the provided bbox center
        target_cx = x + w / 2
        target_cy = y + h / 2
        best_dist = float("inf")
        best_age = None
        best_gender = None

        # Check faces first
        for ind in detected_objects.get_bboxes_inds("face"):
            bbox = detected_objects.yolo_results.boxes[ind].xyxy[0].cpu().numpy()
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            dist = ((cx - target_cx) ** 2 + (cy - target_cy) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_age = detected_objects.ages[ind]
                best_gender = detected_objects.genders[ind]

        # Also check persons (body-based estimation)
        for ind in detected_objects.get_bboxes_inds("person"):
            bbox = detected_objects.yolo_results.boxes[ind].xyxy[0].cpu().numpy()
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            dist = ((cx - target_cx) ** 2 + (cy - target_cy) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_age = detected_objects.ages[ind]
                best_gender = detected_objects.genders[ind]

        # Only accept if the match is reasonably close (within 2x the bbox diagonal)
        max_dist = ((w ** 2 + h ** 2) ** 0.5) * 2
        if best_age is not None and best_dist <= max_dist:
            return {
                "age": round(float(best_age), 1),
                "gender": str(best_gender) if best_gender is not None else None,
                "match_distance": round(float(best_dist), 1),
            }

        return {"age": None, "gender": None, "note": "No matching face/person found near bbox"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
