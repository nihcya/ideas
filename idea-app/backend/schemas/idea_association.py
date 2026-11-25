from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class IdeaAssociationCreate(BaseModel):
    source_idea_id: uuid.UUID
    note: str | None = Field(None, max_length=1000)
