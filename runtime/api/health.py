"""Health API for APEX Runtime."""

from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "uptime": 0.0,
        "gpu": True,
        "memory": "ok",
        "model": "loaded",
        "queue": "active",
        "runtime": "stable",
        "workers": 1
    }
