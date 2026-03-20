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
        detected_objects, _ = predictor.recognize(cv2_img)

        results = []
        face_inds = detected_objects.get_bboxes_inds("face")
        for ind in face_inds:
            bbox = detected_objects.yolo_results.boxes[ind].xyxy[0].cpu().numpy()
            age = detected_objects.ages[ind]
            gender = detected_objects.genders[ind]
            conf = float(detected_objects.yolo_results.boxes[ind].conf[0])

            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
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

        return {"faces": results, "count": len(results)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}")


@app.post("/analyze-crop")
async def analyze_crop(file: UploadFile = File(...)):
    """Analyze a pre-cropped face for age and gender.
    Even for crops, MiVOLO runs its own detector — it needs to find the face."""
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    try:
        predictor = _get_predictor()
        cv2_img = _pil_to_cv2(img)
        detected_objects, _ = predictor.recognize(cv2_img)

        face_inds = detected_objects.get_bboxes_inds("face")
        if face_inds:
            ind = face_inds[0]
            return {
                "age": round(float(detected_objects.ages[ind]), 1) if detected_objects.ages[ind] is not None else None,
                "gender": detected_objects.genders[ind],
            }

        # No face found in crop — try person indices (MiVOLO can estimate from body)
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
