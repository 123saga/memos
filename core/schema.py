from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MemorySource(str, Enum):
    CLAUDE   = "claude"
    CHATGPT  = "chatgpt"
    GEMINI   = "gemini"
    OBSIDIAN = "obsidian"
    MANUAL   = "manual"


class MemoryCategory(str, Enum):
    PROFESSIONAL = "professional"
    PERSONAL     = "personal"
    PREFERENCE   = "preference"
    PROJECT      = "project"
    RELATIONSHIP = "relationship"


class Memory(BaseModel):
    id:         str            = Field(default_factory=lambda: str(uuid4()))
    content:    str
    source:     MemorySource
    category:   MemoryCategory
    tags:       list[str]      = Field(default_factory=list)
    sensitive:  bool           = Field(default=False)
    confidence: float          = Field(default=0.8, ge=0.0, le=1.0)
    embedding:  Optional[list[float]] = Field(default=None, exclude=True)
    created_at: datetime       = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime       = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_raw: Optional[str]  = None

    model_config = {"use_enum_values": True}

    def to_context_string(self) -> str:
        return f"[{self.category.upper()}] {self.content}"

    def age_days(self) -> int:
        return (datetime.now(timezone.utc) - self.created_at).days

    def is_stale(self, threshold_days: int = 180) -> bool:
        return self.age_days() > threshold_days
