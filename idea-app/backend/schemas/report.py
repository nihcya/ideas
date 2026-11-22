from typing import Literal
from pydantic import BaseModel, Field


class IdeaReportCreate(BaseModel):
    idea_id: str
    reason: Literal["spam", "harassment", "copyright", "privacy", "misinformation", "other"]
    description: str | None = Field(None, max_length=2000)


class IdeaReportReview(BaseModel):
    status: Literal["in_review", "resolved", "dismissed"]
    hide_idea: bool = False
    resolution_note: str | None = Field(None, max_length=2000)
