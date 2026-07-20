"""Validation utilities for APEX API."""

from fastapi import Request, HTTPException
from runtime.api.errors import openai_error_response

async def validate_content_type(request: Request, expected: str = "application/json"):
    content_type = request.headers.get("content-type", "")
    if expected not in content_type:
        raise HTTPException(status_code=400, detail=f"Invalid content type. Expected {expected}")
