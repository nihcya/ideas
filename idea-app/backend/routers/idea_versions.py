"""Author-controlled version draft, review, publication and attribution APIs."""
from __future__ import annotations

import uuid
import difflib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Idea, IdeaContribution, IdeaVersion, IdeaVersionContribution
from services.audit_service import audit_content, write_audit_log

router = APIRouter(prefix="/ideas/{idea_id}/versions", tags=["idea-versions"])


class VersionDraftCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=300)
    change_summary: str | None = Field(None, max_length=2000)
    contribution_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class VersionDraftUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=300)
    change_summary: str | None = Field(None, max_length=2000)
    contribution_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


def _not_found():
    return HTTPException(status_code=404, detail={"error": {"code": "VERSION_NOT_FOUND", "message": "版本不存在或无权访问"}})


async def _owned_private_idea(db: AsyncSession, idea_id: uuid.UUID, user: User) -> Idea:
    # Versioning currently follows the private async-collaboration workflow.
    result = await db.execute(select(Idea).where(Idea.id == idea_id))
    idea = result.scalar_one_or_none()
    if idea is None or idea.author_id != user.id or idea.visibility != "private" or idea.status == "rejected" or idea.publication_status == "archived":
        raise _not_found()
    return idea


async def _attach_contributions(db: AsyncSession, version: IdeaVersion, idea_id: uuid.UUID, ids: list[uuid.UUID]):
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail={"error": {"code": "DUPLICATE_CONTRIBUTION", "message": "贡献不能重复选择"}})
    if not ids:
        return
    consumed = await db.execute(select(IdeaVersionContribution.contribution_id).where(IdeaVersionContribution.contribution_id.in_(ids)))
    if consumed.scalars().all():
        raise HTTPException(status_code=409, detail={"error": {"code": "CONTRIBUTION_ALREADY_USED", "message": "所选贡献已归属其他已发布版本"}})
    result = await db.execute(
        select(IdeaContribution, User.username)
        .join(User, User.id == IdeaContribution.author_id)
        .where(IdeaContribution.idea_id == idea_id, IdeaContribution.id.in_(ids), IdeaContribution.status == "accepted")
    )
    rows = result.all()
    if len(rows) != len(ids):
        raise HTTPException(status_code=409, detail={"error": {"code": "CONTRIBUTION_NOT_ACCEPTED", "message": "只能选择当前创意中已采纳的贡献"}})
    for contribution, username in rows:
        db.add(IdeaVersionContribution(
            version_id=version.id,
            contribution_id=contribution.id,
            author_id_snapshot=contribution.author_id,
            author_name_snapshot=username,
            content_snapshot=contribution.content,
        ))


def _version_payload(version: IdeaVersion, attributions: list[IdeaVersionContribution]):
    return {
        "id": str(version.id),
        "idea_id": str(version.idea_id),
        "version_number": version.version_number,
        "content": version.content_snapshot,
        "change_summary": version.change_summary,
        "status": version.status,
        "created_at": version.created_at,
        "published_at": version.published_at,
        "attributions": [
            {
                "contribution_id": str(item.contribution_id),
                "author_id": str(item.author_id_snapshot),
                "author_name": item.author_name_snapshot,
                "content": item.content_snapshot,
            } for item in attributions
        ],
    }


@router.get("")
async def list_versions(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await _owned_private_idea(db, idea_id, user)
    result = await db.execute(select(IdeaVersion).where(IdeaVersion.idea_id == idea_id).order_by(IdeaVersion.version_number.desc()))
    versions = result.scalars().all()
    items = []
    for version in versions:
        attr_result = await db.execute(select(IdeaVersionContribution).where(IdeaVersionContribution.version_id == version.id))
        items.append(_version_payload(version, attr_result.scalars().all()))
    return {"items": items}


@router.get("/{version_id}/diff")
async def compare_published_versions(
    idea_id: uuid.UUID,
    version_id: uuid.UUID,
    against_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compare two immutable published snapshots belonging to the same private Idea."""
    await _owned_private_idea(db, idea_id, user)
    ids = {version_id, against_version_id}
    if len(ids) != 2:
        raise HTTPException(status_code=422, detail={"error": {"code": "SAME_VERSION", "message": "请选择两个不同版本进行对比"}})
    result = await db.execute(
        select(IdeaVersion).where(
            IdeaVersion.idea_id == idea_id,
            IdeaVersion.id.in_(ids),
            IdeaVersion.status == "published",
        )
    )
    versions = {item.id: item for item in result.scalars().all()}
    if len(versions) != 2:
        raise _not_found()
    target = versions[version_id]
    baseline = versions[against_version_id]
    matcher = difflib.SequenceMatcher(
        a=baseline.content_snapshot,
        b=target.content_snapshot,
        autojunk=False,
    )
    segments = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        segments.append({
            "type": tag,
            "old_text": baseline.content_snapshot[i1:i2],
            "new_text": target.content_snapshot[j1:j2],
        })
    return {
        "idea_id": str(idea_id),
        "from_version": {"id": str(baseline.id), "version_number": baseline.version_number},
        "to_version": {"id": str(target.id), "version_number": target.version_number},
        "segments": segments,
    }


@router.post("/drafts", status_code=201)
async def create_version_draft(idea_id: uuid.UUID, req: VersionDraftCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    idea_result = await db.execute(select(Idea).where(Idea.id == idea_id).with_for_update())
    idea = idea_result.scalar_one_or_none()
    if idea is None or idea.author_id != user.id or idea.visibility != "private" or idea.status == "rejected" or idea.publication_status == "archived":
        raise _not_found()
    existing = await db.execute(select(IdeaVersion.id).where(IdeaVersion.idea_id == idea_id, IdeaVersion.status == "draft").limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"error": {"code": "DRAFT_EXISTS", "message": "该创意已有未发布版本草稿，请先编辑或发布"}})
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail={"error": {"code": "EMPTY_VERSION", "message": "版本内容不能为空"}})
    passed, reason = await audit_content(db, content)
    if not passed:
        await write_audit_log(db, idea.id, content, False, reason)
        raise HTTPException(status_code=403, detail={"error": {"code": "AUDIT_FAILED", "message": reason or "版本内容审核不通过"}})
    max_result = await db.execute(select(func.max(IdeaVersion.version_number)).where(IdeaVersion.idea_id == idea_id))
    number = (max_result.scalar() or 0) + 1
    version = IdeaVersion(idea_id=idea_id, version_number=number, content_snapshot=content, change_summary=req.change_summary, status="draft", created_by=user.id)
    db.add(version)
    await db.flush()
    await _attach_contributions(db, version, idea_id, req.contribution_ids)
    await write_audit_log(db, idea.id, content, True, None)
    await db.commit()
    await db.refresh(version)
    attr_result = await db.execute(select(IdeaVersionContribution).where(IdeaVersionContribution.version_id == version.id))
    return _version_payload(version, attr_result.scalars().all())


@router.patch("/{version_id}")
async def update_version_draft(idea_id: uuid.UUID, version_id: uuid.UUID, req: VersionDraftUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    idea = await _owned_private_idea(db, idea_id, user)
    result = await db.execute(select(IdeaVersion).where(IdeaVersion.id == version_id, IdeaVersion.idea_id == idea_id, IdeaVersion.status == "draft").with_for_update())
    version = result.scalar_one_or_none()
    if version is None:
        raise _not_found()
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail={"error": {"code": "EMPTY_VERSION", "message": "版本内容不能为空"}})
    passed, reason = await audit_content(db, content)
    if not passed:
        await write_audit_log(db, idea.id, content, False, reason)
        raise HTTPException(status_code=403, detail={"error": {"code": "AUDIT_FAILED", "message": reason or "版本内容审核不通过"}})
    old = await db.execute(select(IdeaVersionContribution).where(IdeaVersionContribution.version_id == version.id))
    for item in old.scalars().all():
        await db.delete(item)
    version.content_snapshot = content
    version.change_summary = req.change_summary
    await db.flush()
    await _attach_contributions(db, version, idea_id, req.contribution_ids)
    await write_audit_log(db, idea.id, content, True, None)
    await db.commit()
    return {"updated": True, "id": str(version.id), "status": version.status}


@router.post("/{version_id}/publish")
async def publish_version(idea_id: uuid.UUID, version_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    idea_result = await db.execute(select(Idea).where(Idea.id == idea_id).with_for_update())
    idea = idea_result.scalar_one_or_none()
    if idea is None or idea.author_id != user.id or idea.visibility != "private" or idea.status == "rejected" or idea.publication_status == "archived":
        raise _not_found()
    version_result = await db.execute(select(IdeaVersion).where(IdeaVersion.id == version_id, IdeaVersion.idea_id == idea_id, IdeaVersion.status == "draft").with_for_update())
    version = version_result.scalar_one_or_none()
    if version is None:
        raise _not_found()
    attr_result = await db.execute(select(IdeaVersionContribution).where(IdeaVersionContribution.version_id == version.id))
    attributions = attr_result.scalars().all()
    if attributions:
        contribution_ids = [item.contribution_id for item in attributions]
        current = await db.execute(select(IdeaContribution.id).where(IdeaContribution.id.in_(contribution_ids), IdeaContribution.idea_id == idea_id, IdeaContribution.status == "accepted").with_for_update())
        if len(current.scalars().all()) != len(contribution_ids):
            raise HTTPException(status_code=409, detail={"error": {"code": "CONTRIBUTION_STATE_CHANGED", "message": "关联贡献状态已变化，请重新编辑草稿"}})
    version.status = "published"
    version.published_by = user.id
    version.published_at = datetime.now(timezone.utc)
    idea.content = version.content_snapshot
    await db.commit()
    return {"published": True, "idea_id": str(idea_id), "version": _version_payload(version, attributions), "idea_content": idea.content}
