"""Runtime status API for APEX Runtime."""

from fastapi import APIRouter

router = APIRouter()

@router.get("/runtime")
async def runtime_status():
    """Runtime status endpoint."""
    return {
        "loaded_model": "apex-default",
        "vram": "4GB",
        "cpu": "10%",
        "ram": "8GB",
        "tokenizer": "fast",
        "engine": "transformers",
        "device": "cuda:0",
        "precision": "bf16",
        "queue": 0,
        "transport": "http",
        "api_version": "v1"
    }
