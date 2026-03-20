"""
MiVOLO Age & Gender Estimation API
Standalone microservice — not yet connected to the main app.

Endpoints:
  POST /analyze  — upload an image, get detected faces with age/gender
  GET  /health   — health check
"""
import os
import io
import tempfile
from typing import Optional

import torch
import numpy as np
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="MiVOLO Age Estimation", version="1.0")

# Lazy-loaded models
_predictor = None
_detector = None


def _get_models():
    global _predictor, _detector
    if _predictor is not None:
        return _predictor, _detector

    from mivolo.predictor import Predictor

    device = "cuda" if torch.cuda.is_available() else "cpu"

    _predictor = Predictor(
        config=None,
        detector_weights="/app/models/yolov8x_person_face.pt",
        checkpoint="/app/models/mivolo_imdb.pth.tar",
        device=device,
        with_persons=True,
        disable_faces=False,
    )
    _detector = None  # Predictor handles detection internally

    return _predictor, _detector


@app.get("/health")
async def health():
    return {"status": "ok", "model": "MiVOLO", "gpu": torch.cuda.is_available()}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """Analyze an image for faces with age and gender estimation."""
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    # Save to temp file (MiVOLO expects file path)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp, format="JPEG", quality=95)
        tmp_path = tmp.name

    try:
        predictor, _ = _get_models()

        # Run prediction
        detected_objects, _ = predictor.recognize(tmp_path)

        results = []
        if detected_objects is not None:
            for obj in detected_objects:
                face_data = {
                    "age": round(obj.age, 1) if obj.age is not None else None,
                    "gender": obj.gender if hasattr(obj, "gender") else None,
                    "bbox": {
                        "x": int(obj.bbox[0]),
                        "y": int(obj.bbox[1]),
                        "w": int(obj.bbox[2] - obj.bbox[0]),
                        "h": int(obj.bbox[3] - obj.bbox[1]),
                    } if obj.bbox is not None else None,
                    "confidence": float(obj.det_score) if hasattr(obj, "det_score") else None,
                }
                results.append(face_data)

        return {"faces": results, "count": len(results)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        os.unlink(tmp_path)


@app.post("/analyze-crop")
async def analyze_crop(file: UploadFile = File(...)):
    """Analyze a pre-cropped face image for age estimation only.
    Skips face detection — assumes the entire image is a face."""
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp, format="JPEG", quality=95)
        tmp_path = tmp.name

    try:
        predictor, _ = _get_models()
        detected_objects, _ = predictor.recognize(tmp_path)

        if detected_objects and len(detected_objects) > 0:
            obj = detected_objects[0]
            return {
                "age": round(obj.age, 1) if obj.age is not None else None,
                "gender": obj.gender if hasattr(obj, "gender") else None,
            }
        else:
            return {"age": None, "gender": None, "note": "No face detected in crop"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        os.unlink(tmp_path)
