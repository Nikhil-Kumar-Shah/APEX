"""OpenAI-compatible Pydantic schemas."""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

class CompletionRequest(BaseModel):
    model: str
    prompt: Union[str, List[str]]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = 16
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 1686935002
    owned_by: str = "apex"

class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelInfo]
