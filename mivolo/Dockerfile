FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch (CPU for now — swap for CUDA if GPU available)
RUN pip install --no-cache-dir \
    torch==2.1.2 \
    torchvision==0.16.2 \
    --index-url https://download.pytorch.org/whl/cpu

# Clone MiVOLO
RUN git clone https://github.com/WildChlamydia/MiVOLO.git /app/mivolo

# Install MiVOLO dependencies
WORKDIR /app/mivolo
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

# Install FastAPI for the API wrapper
RUN pip install --no-cache-dir fastapi==0.115.6 uvicorn==0.34.0 python-multipart==0.0.20

# Download model weights
RUN mkdir -p /app/models && \
    wget -q "https://github.com/WildChlamydia/MiVOLO/releases/download/v1.0/yolov8x_person_face.pt" -O /app/models/yolov8x_person_face.pt && \
    wget -q "https://github.com/WildChlamydia/MiVOLO/releases/download/v1.0/model_imdb_cross_person_4.22_99.46.pth.tar" -O /app/models/mivolo_imdb.pth.tar

WORKDIR /app

# Copy API wrapper
COPY api.py /app/api.py

EXPOSE 8010

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8010"]
