from __future__ import annotations

import uuid
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class CollaborationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=4000)
    source_idea_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=10)


class CollaborationMemberInvite(BaseModel):
    user_id: uuid.UUID
    role: Literal["contributor", "viewer"] = "contributor"


class CollaborationContributionCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    contribution_type: Literal["idea", "revision", "comment", "research"] = "idea"
    source_idea_id: uuid.UUID | None = None
    note: str | None = Field(None, max_length=2000)


class CollaborationContributionUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    contribution_type: Literal["idea", "revision", "comment", "research"] = "idea"
    source_idea_id: uuid.UUID | None = None
    note: str | None = Field(None, max_length=2000)


class CollaborationContributionReview(BaseModel):
    decision: Literal["accepted", "rejected"]
    review_note: str | None = Field(None, max_length=2000)


class CollaborationMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    role: str
    status: str

class CollaborationPublish(BaseModel):
    content: str = Field(..., min_length=1, max_length=300)
    change_summary: str | None = Field(None, max_length=2000)
    visibility: Literal["private", "public"] = "private"
    license_code: Literal[
        "all_rights_reserved", "attribution", "attribution_adaptation", "custom"
    ]
    license_custom_text: str | None = Field(None, max_length=5000)
    license_version: str = Field("v1", min_length=1, max_length=32)
    allow_fork: bool = False
    confirm_terms: bool = False
    confirm_custom_licenses: bool = False
    accepted_contribution_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
