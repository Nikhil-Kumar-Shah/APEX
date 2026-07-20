"""Version API for APEX Runtime."""

from fastapi import APIRouter

router = APIRouter()

@router.get("/version")
async def version():
    """API and Runtime Version."""
    return {
        "runtime_version": "1.2",
        "api_version": "v1",
        "build": "stable",
        "commit": "HEAD",
        "compatibility": ["openai"]
    }
