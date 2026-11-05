"""Chat API for APEX Runtime — OpenAI-compatible completions & conversation management."""

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from runtime.api.schemas import ChatCompletionRequest, ConversationCreateRequest
from runtime.api.serializers import serialize_chat_completion, serialize_chat_completion_chunk
from runtime.memory.conversation import ConversationMemoryManager
from runtime.memory.errors import ConversationNotFoundError

logger = logging.getLogger("runtime.api.chat")
router = APIRouter()

# Default maximum message turns to retain in context window
MAX_CONTEXT_TURNS = 16


def _get_memory() -> ConversationMemoryManager:
    """Resolves workspace conversation memory manager."""
    ws_dir = Path.cwd() / "workspaces" / "default"
    return ConversationMemoryManager(ws_dir)


def format_chat_prompt(messages: List[Any], tokenizer: Any = None) -> str:
    """Formats chat messages into an instruction prompt."""
    raw_msgs = []
    for m in messages:
        if isinstance(m, dict):
            raw_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        else:
            raw_msgs.append({"role": getattr(m, "role", "user"), "content": getattr(m, "content", "")})

    if tokenizer and hasattr(tokenizer, "apply_chat_template") and callable(tokenizer.apply_chat_template):
        try:
            return tokenizer.apply_chat_template(raw_msgs, tokenize=False, add_generation_prompt=True)
        except Exception:
            pass

    # Standard ChatML fallback prompt (Qwen, DeepSeek, etc.)
    parts = []
    for msg in raw_msgs:
        role = msg["role"]
        content = msg["content"]
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    parts.append("<|im_start|>assistant")
    return "\n".join(parts) + "\n"


def apply_context_window_guard(raw_msgs: List[Dict[str, str]], max_turns: int = MAX_CONTEXT_TURNS) -> List[Dict[str, str]]:
    """Applies sliding window context retention to protect model context limit."""
    if len(raw_msgs) <= max_turns:
        return raw_msgs

    # Preserve system instruction if present at position 0
    guarded: List[Dict[str, str]] = []
    start_idx = 0
    if raw_msgs[0].get("role") == "system":
        guarded.append(raw_msgs[0])
        start_idx = 1

    # Take the most recent (max_turns - len(guarded)) turns
    remaining_slots = max_turns - len(guarded)
    recent_msgs = raw_msgs[start_idx:][-remaining_slots:]
    guarded.extend(recent_msgs)
    return guarded


# ── Conversation Management Endpoints ────────────────────────────────────

@router.get("/v1/conversations")
async def list_conversations():
    """Lists all stored conversation sessions in the active workspace."""
    memory = _get_memory()
    convos = memory.list_conversations()
    # Sort reverse chronological
    convos.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return {"object": "list", "data": convos}


@router.post("/v1/conversations")
async def create_conversation(req: ConversationCreateRequest):
    """Initializes a new conversation session."""
    memory = _get_memory()
    convo = memory.create_conversation(title=req.title or "New Conversation")
    return convo


@router.get("/v1/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Retrieves full message history of a specific conversation."""
    memory = _get_memory()
    try:
        return memory.load_conversation(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")


@router.delete("/v1/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Deletes a conversation history session."""
    memory = _get_memory()
    deleted = memory.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
    return {"id": conversation_id, "object": "conversation", "deleted": True}


# ── Chat Completions Endpoint ─────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """OpenAI-compatible Chat Completions with real token streaming & context persistence."""
    model_manager = getattr(req.app.state, "model_manager", None)
    active_engine = getattr(model_manager, "active_engine", None) if model_manager else None

    # Check if a model engine is loaded and active
    if active_engine and getattr(active_engine, "is_loaded", False):
        raw_msgs = []
        for m in request.messages:
            if isinstance(m, dict):
                raw_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
            else:
                raw_msgs.append({"role": getattr(m, "role", "user"), "content": getattr(m, "content", "")})

        # Apply sliding window context guard
        guarded_msgs = apply_context_window_guard(raw_msgs)

        gen_params = {
            "max_new_tokens": getattr(request, "max_tokens", 512) or 512,
            "temperature": getattr(request, "temperature", 0.7) or 0.7,
            "top_p": getattr(request, "top_p", 0.9) or 0.9,
        }

        memory = _get_memory()
        convo_id = request.conversation_id

        # Persist incoming user turn if conversation_id provided
        if convo_id and raw_msgs:
            try:
                last_user_msg = next((m for m in reversed(raw_msgs) if m["role"] == "user"), None)
                if last_user_msg:
                    memory.append_message(convo_id, "user", last_user_msg["content"])
            except Exception as e:
                logger.warning(f"Failed to record user turn in memory: {e}")

        if request.stream:
            async def generate_real_stream():
                loop = asyncio.get_running_loop()
                token_queue = asyncio.Queue()
                accumulated_text: List[str] = []

                def _produce_tokens():
                    try:
                        for token in active_engine.generate_stream(guarded_msgs, gen_params):
                            loop.call_soon_threadsafe(token_queue.put_nowait, token)
                    except Exception as exc:
                        loop.call_soon_threadsafe(token_queue.put_nowait, exc)
                    finally:
                        loop.call_soon_threadsafe(token_queue.put_nowait, None)

                # Run synchronous generation in background thread
                threading.Thread(target=_produce_tokens, daemon=True).start()

                # Initial role chunk
                yield f"data: {json.dumps(serialize_chat_completion_chunk(request.model, role='assistant'))}\n\n"

                while True:
                    token = await token_queue.get()
                    if token is None:
                        break
                    if isinstance(token, Exception):
                        raise token
                    if await req.is_disconnected():
                        logger.info("Client disconnected during stream. Halting token delivery.")
                        break
                    if token:
                        accumulated_text.append(token)
                        yield f"data: {json.dumps(serialize_chat_completion_chunk(request.model, content=token))}\n\n"

                # Persist assistant turn if conversation_id was provided
                full_response = "".join(accumulated_text)
                if convo_id and full_response:
                    try:
                        memory.append_message(convo_id, "assistant", full_response)
                    except Exception as e:
                        logger.warning(f"Failed to record assistant turn in memory: {e}")

                yield f"data: {json.dumps(serialize_chat_completion_chunk(request.model, finish_reason='stop'))}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(generate_real_stream(), media_type="text/event-stream")
        else:
            full_text = ""
            for token in active_engine.generate_stream(guarded_msgs, gen_params):
                full_text += token

            if convo_id and full_text:
                try:
                    memory.append_message(convo_id, "assistant", full_text)
                except Exception as e:
                    logger.warning(f"Failed to record assistant turn in memory: {e}")

            return serialize_chat_completion(
                model=request.model,
                content=full_text,
                prompt_tokens=10,
                completion_tokens=len(full_text.split()),
            )

    # Return HTTP 503 if no active model is loaded
    raise HTTPException(
        status_code=503,
        detail="Model is currently loading or not ready in APEX runtime. Please retry in a few moments.",
        headers={"Retry-After": "5"},
    )
