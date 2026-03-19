from fastapi import APIRouter, Request

from services.timeline_builder import build_timeline

router = APIRouter()


@router.get("/timeline")
async def get_timeline(request: Request):
    """Get the full timeline with photos grouped by era."""
    username = request.state.username
    return await build_timeline(username)


@router.post("/timeline/rebuild")
async def rebuild_timeline(request: Request):
    """Force rebuild the timeline from current data."""
    username = request.state.username
    return await build_timeline(username)
