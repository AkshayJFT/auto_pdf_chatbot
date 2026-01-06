from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid

class ConversationMode(str, Enum):
    PRESENTATION = "presentation"
    RAG = "rag"

class ConversationState(BaseModel):
    conversation_id: str
    mode: ConversationMode = ConversationMode.PRESENTATION
    current_segment: int = 0
    presentation_paused: bool = False
    paused_at_segment: Optional[int] = None
    paused_mid_segment: bool = False  # Flag to indicate mid-segment pause
    pause_timestamp: Optional[float] = None  # When the pause occurred
    interrupted_segment_text: Optional[str] = None  # Text of interrupted segment for resume
    interrupted_at_position: Optional[int] = None  # Position where interruption occurred
    created_at: Optional[float] = None

class UserMessage(BaseModel):
    text: str
    audio: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    command: Optional[str] = None

class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: float

class BotResponse(BaseModel):
    type: str  # "presentation", "rag_answer", "error"
    text: str
    images: List[str] = []
    segment_id: Optional[int] = None
    sources: Optional[List[str]] = None

class PresentationSegment(BaseModel):
    id: int
    text: str
    images: List[str] = []
    duration_seconds: int = 5
    pdf_page: Optional[int] = None
    pdf_name: Optional[str] = None

class PricingRequest(BaseModel):
    windows: List[Dict[str, Any]]

class WindowConfig(BaseModel):
    type: str
    size: str
    quantity: int = 1
    
    def dict(self):
        return {
            "type": self.type,
            "size": self.size,
            "quantity": self.quantity
        }