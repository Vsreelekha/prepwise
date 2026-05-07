"""
Scoring endpoints.

This router provides scoring-related placeholder endpoints until the full
scoring module is completed.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/health")
def scoring_health() -> dict:
    """Quick endpoint to verify scoring router wiring."""
    return {"status": "scoring router ready"}

