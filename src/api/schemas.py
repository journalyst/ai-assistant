from pydantic import BaseModel
from typing import Optional, Any

class ChatRequest(BaseModel):
    user_id: int
    query: str
    user_name: str = "Trader"
    stream: bool = False  # Enable streaming response
    session_id: Optional[str] = None  # Session ID for conversation history

class ChatResponse(BaseModel):
    response: str
    data: dict
    metadata: dict

class StreamEvent(BaseModel):
    """Server-Sent Event structure for streaming responses."""
    event: str  # "start", "chunk", "data", "done", "error"
    data: Any