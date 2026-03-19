from fastapi import APIRouter

from services.timeline_builder import build_timeline

router = APIRouter()


@router.get("/timeline")
async def get_timeline():
    """Get the full timeline with photos grouped by era."""
    return await build_timeline()


@router.post("/timeline/rebuild")
async def rebuild_timeline():
    """Force rebuild the timeline from current data."""
    return await build_timeline()
