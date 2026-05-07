"""
Roadmap endpoints.

This router provides roadmap-related placeholder endpoints until the full
roadmap feature is implemented.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


@router.get("/health")
def roadmap_health() -> dict:
    """Quick endpoint to verify roadmap router wiring."""
    return {"status": "roadmap router ready"}

