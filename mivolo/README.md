# MiVOLO Age Estimation Service

Standalone microservice for age & gender estimation using MiVOLO (SOTA transformer model).

## Status: Prepared, NOT connected to main app

## Quick Start

```bash
cd mivolo
docker compose up --build
```

First build downloads ~500MB of model weights. Subsequent starts are fast.

## API

### `POST /analyze`
Upload a full image. Returns detected faces with age, gender, bbox, confidence.

```bash
curl -X POST -F "file=@photo.jpg" http://localhost:8010/analyze
```

Response:
```json
{
  "faces": [
    {"age": 25.3, "gender": "female", "bbox": {"x": 100, "y": 50, "w": 80, "h": 100}, "confidence": 0.95}
  ],
  "count": 1
}
```

### `POST /analyze-crop`
Upload a pre-cropped face image. Returns age and gender only.

```bash
curl -X POST -F "file=@face_crop.jpg" http://localhost:8010/analyze-crop
```

### `GET /health`
```bash
curl http://localhost:8010/health
```

## Integration Plan

When ready to connect to the main app:
1. Add `mivolo` service to main `docker-compose.yml`
2. Update `backend/services/age_estimation.py` to call `http://mivolo:8010/analyze-crop`
3. Replace DeepFace age estimation with MiVOLO results
4. Optionally use MiVOLO's face detection (YOLOv8) instead of RetinaFace

## GPU Support

Uncomment the `deploy` section in `docker-compose.yml` for NVIDIA GPU acceleration.
The Dockerfile uses CPU PyTorch by default — swap the pip install line for CUDA wheels.
