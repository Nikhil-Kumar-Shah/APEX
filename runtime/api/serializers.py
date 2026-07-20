"""Response formatting and serializers."""

import time
import uuid
from typing import List, Dict, Any

def serialize_chat_completion(
    model: str, 
    content: str, 
    finish_reason: str = "stop",
    prompt_tokens: int = 0,
    completion_tokens: int = 0
) -> Dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": finish_reason
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    }
