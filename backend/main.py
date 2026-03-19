import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from models.schema import init_db, get_user_dir, _sanitize_username
from routers import upload, process, tag, timeline, manage


DATA_DIR = os.environ.get("DATA_DIR", "/data")


class UserMiddleware(BaseHTTPMiddleware):
    """Extract X-User header and attach to request state."""
    async def dispatch(self, request: Request, call_next):
        username = request.headers.get("X-User", "default") or "default"
        request.state.username = _sanitize_username(username)
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="LumaLife", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(UserMiddleware)

os.makedirs(os.path.join(DATA_DIR, "users"), exist_ok=True)


@app.get("/data/{path:path}")
async def serve_user_data(path: str, request: Request):
    """Serve user-specific data files."""
    username = request.state.username
    user_dir = get_user_dir(username)
    file_path = os.path.join(user_dir, path)
    if not os.path.isfile(file_path):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(file_path)


app.include_router(upload.router, prefix="/api/photos", tags=["upload"])
app.include_router(process.router, prefix="/api/photos", tags=["process"])
app.include_router(tag.router, prefix="/api/photos", tags=["tag"])
app.include_router(timeline.router, prefix="/api", tags=["timeline"])
app.include_router(manage.router, prefix="/api", tags=["manage"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/users")
async def list_users():
    """List all user sessions."""
    users_dir = os.path.join(DATA_DIR, "users")
    if not os.path.isdir(users_dir):
        return {"users": []}
    users = [d for d in os.listdir(users_dir) if os.path.isdir(os.path.join(users_dir, d))]
    return {"users": sorted(users)}
