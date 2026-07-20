"""Server-Sent Events (SSE) streaming logic."""

import json
from typing import AsyncGenerator

async def generate_sse(generator: AsyncGenerator[dict, None]) -> AsyncGenerator[str, None]:
    """Wraps a dictionary generator into Server-Sent Events."""
    async for chunk in generator:
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"
