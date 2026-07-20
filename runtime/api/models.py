"""Models API for APEX Runtime."""

import time
from fastapi import APIRouter
from runtime.api.schemas import ModelList, ModelInfo

router = APIRouter()

@router.get("/v1/models", response_model=ModelList)
async def list_models():
    """List available and loaded models."""
    return ModelList(data=[
        ModelInfo(
            id="apex-runtime-model",
            object="model",
            created=int(time.time()),
            owned_by="apex"
        )
    ])

@router.get("/v1/models/{model_id}", response_model=ModelInfo)
async def get_model(model_id: str):
    """Get details for a specific model."""
    return ModelInfo(
        id=model_id,
        object="model",
        created=int(time.time()),
        owned_by="apex"
    )
