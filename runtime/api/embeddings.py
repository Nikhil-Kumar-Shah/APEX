"""Embeddings API for APEX Runtime."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Union, List

router = APIRouter()

class EmbeddingRequest(BaseModel):
    model: str
    input: Union[str, List[str]]
    user: str = None

@router.post("/v1/embeddings")
async def embeddings(request: EmbeddingRequest):
    """OpenAI-compatible embeddings."""
    return {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "index": 0,
                "embedding": [0.0] * 1536
            }
        ],
        "model": request.model,
        "usage": {
            "prompt_tokens": 8,
            "total_tokens": 8
        }
    }
