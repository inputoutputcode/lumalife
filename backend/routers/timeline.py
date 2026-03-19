from fastapi import APIRouter, Request

from services.timeline_builder import build_timeline

router = APIRouter()


@router.get("/timeline")
async def get_timeline(request: Request):
    """Get the full timeline with photos grouped by era."""
    user_id = request.state.user_id
    return await build_timeline(user_id)


@router.post("/timeline/rebuild")
async def rebuild_timeline(request: Request):
    """Force rebuild the timeline from current data."""
    user_id = request.state.user_id
    return await build_timeline(user_id)
