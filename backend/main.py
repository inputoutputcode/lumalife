import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from models.schema import init_db
from routers import upload, process, tag, timeline, manage


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="LumaLife", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://frontend:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_dir = os.environ.get("DATA_DIR", "/data")
os.makedirs(os.path.join(data_dir, "uploads"), exist_ok=True)
os.makedirs(os.path.join(data_dir, "processed"), exist_ok=True)
os.makedirs(os.path.join(data_dir, "embeddings"), exist_ok=True)

app.mount("/data", StaticFiles(directory=data_dir), name="data")

app.include_router(upload.router, prefix="/api/photos", tags=["upload"])
app.include_router(process.router, prefix="/api/photos", tags=["process"])
app.include_router(tag.router, prefix="/api/photos", tags=["tag"])
app.include_router(timeline.router, prefix="/api", tags=["timeline"])
app.include_router(manage.router, prefix="/api", tags=["manage"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
