from pydantic import BaseModel, field_validator
from typing import Optional, Any

class ChatRequest(BaseModel):
    user_id: str
    query: str
    user_name: str = "Trader"
    stream: bool = False  # Enable streaming response
    session_id: Optional[str] = None  # Session ID for conversation history

    @field_validator("user_id", mode="before")
    @classmethod
    def normalize_user_id(cls, value: Any) -> str:
        """Accept numeric IDs from clients but normalize to non-empty string."""
        if value is None:
            raise ValueError("user_id is required")

        user_id = str(value).strip()
        if not user_id:
            raise ValueError("user_id cannot be empty")
        return user_id

class ChatResponse(BaseModel):
    response: str
    data: dict
    metadata: dict

class StreamEvent(BaseModel):
    """Server-Sent Event structure for streaming responses."""
    event: str  # "start", "chunk", "data", "done", "error"
    data: Any