"""Models API for APEX Runtime."""

import time
from fastapi import APIRouter, Request
from runtime.api.schemas import ModelList, ModelInfo

router = APIRouter()

@router.get("/v1/models", response_model=ModelList)
async def list_models(req: Request = None):
    """List available and loaded models."""
    model_ids = ["apex-runtime-model"]
    if req and hasattr(req.app.state, "model_manager") and req.app.state.model_manager:
        mm = req.app.state.model_manager
        if getattr(mm, "active_model_id", None):
            active_id = mm.active_model_id
            if active_id not in model_ids:
                model_ids.insert(0, active_id)
                
    return ModelList(data=[
        ModelInfo(
            id=m_id,
            object="model",
            created=int(time.time()),
            owned_by="apex"
        ) for m_id in model_ids
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
