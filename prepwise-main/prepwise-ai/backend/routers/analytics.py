"""
Analytics endpoints.

This router provides placeholder analytics endpoints so imports resolve cleanly
while core features are being built.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/health")
def analytics_health() -> dict:
    """Quick endpoint to verify analytics router wiring."""
    return {"status": "analytics router ready"}

