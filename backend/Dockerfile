FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libmagic1 \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads /data/processed /data/embeddings

# Pre-download InsightFace buffalo_l model
RUN python3 -c "\
import insightface; \
app = insightface.app.FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider']); \
app.prepare(ctx_id=0, det_size=(640, 640)); \
print('InsightFace models downloaded') \
" || true

# Pre-download ViT age classifier (good with children)
RUN python3 -c "\
from transformers import ViTImageProcessor, ViTForImageClassification; \
ViTForImageClassification.from_pretrained('nateraw/vit-age-classifier'); \
ViTImageProcessor.from_pretrained('nateraw/vit-age-classifier'); \
print('ViT age classifier downloaded') \
" || true

# Pre-download ViT age classifier (excellent with children)
RUN python3 -c "\
from transformers import ViTImageProcessor, ViTForImageClassification; \
ViTForImageClassification.from_pretrained('nateraw/vit-age-classifier'); \
ViTImageProcessor.from_pretrained('nateraw/vit-age-classifier'); \
print('ViT age classifier downloaded') \
" || true

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
