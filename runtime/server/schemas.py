"""Pydantic schemas for OpenAI API compatibility."""

import time
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ChatCompletionMessage(BaseModel):
    """Represents a single chat message."""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI compatible Chat Completion Request payload."""

    model: str
    messages: List[ChatCompletionMessage]
    stream: bool = False
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(512, ge=1)
    repetition_penalty: float = Field(1.0, ge=0.0, le=2.0)
    stop: Optional[Union[str, List[str]]] = None


class ChatCompletionResponseChoice(BaseModel):
    """Single completion selection."""

    index: int
    message: ChatCompletionMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionUsage(BaseModel):
    """Usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI compatible Chat Completion Response payload."""

    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)


class ChatCompletionStreamDelta(BaseModel):
    """Incremental delta content update."""

    role: Optional[str] = None
    content: Optional[str] = None


class ChatCompletionStreamChoice(BaseModel):
    """Incremental delta choice."""

    index: int
    delta: ChatCompletionStreamDelta
    finish_reason: Optional[str] = None


class ChatCompletionStreamResponse(BaseModel):
    """OpenAI compatible Chat Completion Chunk payload."""

    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionStreamChoice]


class ModelInfo(BaseModel):
    """Hugging Face Model representation metadata."""

    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "custom"


class ModelListResponse(BaseModel):
    """OpenAI compatible Model Listing payload."""

    object: str = "list"
    data: List[ModelInfo]
