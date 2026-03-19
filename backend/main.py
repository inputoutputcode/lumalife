import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from models.schema import init_db, close_db, get_pool, get_or_create_user, get_user_dir, _sanitize_username
from routers import upload, process, tag, timeline, manage


DATA_DIR = os.environ.get("DATA_DIR", "/data")


class UserMiddleware(BaseHTTPMiddleware):
    """Extract X-User header, resolve to user_id, attach to request state."""
    async def dispatch(self, request: Request, call_next):
        username = request.headers.get("X-User", "default") or "default"
        request.state.username = _sanitize_username(username)
        request.state.user_id = await get_or_create_user(request.state.username)
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


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
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT username FROM users ORDER BY username")
        users = [r["username"] for r in rows]
    return {"users": users}
