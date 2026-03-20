FROM nvcr.io/nvidia/vllm:26.01-py3

# vLLM image has PyTorch with sm_121 (GB10/Blackwell) support

RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone MiVOLO
RUN git clone https://github.com/WildChlamydia/MiVOLO.git /app/mivolo

# Install MiVOLO deps (use PYTHONPATH instead of setup.py)
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir \
    huggingface_hub \
    "ultralytics==8.1.0" \
    "timm==0.8.13.dev0" \
    "lapx>=0.5.2" \
    gdown \
    fastapi==0.115.6 \
    uvicorn==0.34.0 \
    python-multipart==0.0.20

# Download model weights
# YOLOv8 face+person detector from HuggingFace
# MiVOLO cross_person (face+body, age+gender) from Google Drive
RUN mkdir -p /app/models && \
    python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download('iitolstykh/YOLO-Face-Person-Detector', 'yolov8x_person_face.pt', local_dir='/app/models')" && \
    gdown "11i8pKctxz3wVkDBlWKvhYIh7kpVFXSZ4" -O /app/models/mivolo_imdb.pth.tar

# Copy API wrapper
COPY api.py /app/api.py

# Add mivolo to Python path
ENV PYTHONPATH="/app/mivolo:${PYTHONPATH}"

EXPOSE 8010

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8010"]
