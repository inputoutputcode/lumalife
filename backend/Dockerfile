FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads /data/processed /data/embeddings

# Pre-download DeepFace model weights to avoid slow first-run downloads
RUN python3 -c "\
from deepface import DeepFace; \
DeepFace.extract_faces('https://raw.githubusercontent.com/serengil/deepface/master/tests/dataset/img1.jpg', detector_backend='ssd', enforce_detection=False); \
DeepFace.represent('https://raw.githubusercontent.com/serengil/deepface/master/tests/dataset/img1.jpg', model_name='ArcFace', detector_backend='ssd', enforce_detection=False) \
" || true

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
