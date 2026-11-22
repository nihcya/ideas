"""First-class asynchronous collaboration workspaces.

Workspace membership is independent from per-Idea ACL grants: accepting a
workspace invitation never grants access to a private source Idea.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import (
    User, Idea, Collaboration, CollaborationMember, CollaborationSource,
    CollaborationContribution, CollaborationEvent,
)
from schemas.collaboration import (
    CollaborationCreate, CollaborationMemberInvite,
    CollaborationContributionCreate, CollaborationContributionUpdate,
    CollaborationContributionReview,
)
from services.idea_access import can_view_idea, get_effective_rights_chain

router = APIRouter(prefix="/collaborations", tags=["collaborations"])


def _error(status_code: int, code: str, message: str):
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


async def _member(db: AsyncSession, collaboration_id: uuid.UUID, user: User, *, roles=None):
    result = await db.execute(
        select(CollaborationMember).where(
            CollaborationMember.collaboration_id == collaboration_id,
            CollaborationMember.user_id == user.id,
            CollaborationMember.status == "accepted",
        ).with_for_update()
    )
    member = result.scalar_one_or_none()
    if member is None or (roles is not None and member.role not in roles):
        raise _error(404, "COLLABORATION_NOT_FOUND", "协作空间不存在或无权访问")
    return member


async def _event(db: AsyncSession, collaboration_id, actor_id, event_type, payload=None):
    db.add(CollaborationEvent(
        collaboration_id=collaboration_id,
        actor_id=actor_id,
        event_type=event_type,
        payload=payload or {},
    ))


def _contribution_payload(item: CollaborationContribution):
    return {
        "id": str(item.id),
        "collaboration_id": str(item.collaboration_id),
        "author_id": str(item.author_id),
        "source_idea_id": str(item.source_idea_id) if item.source_idea_id else None,
        "contribution_type": item.contribution_type,
        "content": item.content,
        "note": item.note,
        "status": item.status,
        "reviewed_by": str(item.reviewed_by) if item.reviewed_by else None,
        "reviewed_at": item.reviewed_at,
        "review_note": item.review_note,
        "created_at": item.created_at,
    }


@router.get("")
async def list_my_collaborations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Collaboration, CollaborationMember.role)
        .join(CollaborationMember, CollaborationMember.collaboration_id == Collaboration.id)
        .where(
            CollaborationMember.user_id == user.id,
            CollaborationMember.status == "accepted",
        )
        .order_by(Collaboration.created_at.desc())
        .limit(100)
    )
    return {"items": [
        {"id": str(row.Collaboration.id), "title": row.Collaboration.title,
         "description": row.Collaboration.description, "status": row.Collaboration.status,
         "visibility": row.Collaboration.visibility, "owner_id": str(row.Collaboration.owner_id),
         "member_role": row.role}
        for row in result.all()
    ]}


@router.post("", status_code=201)
async def create_collaboration(
    payload: CollaborationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if len(set(payload.source_idea_ids)) != len(payload.source_idea_ids):
        raise _error(422, "DUPLICATE_SOURCE", "来源创意不能重复")
    sources = []
    for idea_id in payload.source_idea_ids:
        idea = await db.get(Idea, idea_id)
        if idea is None or not await can_view_idea(db, idea, user.id):
            raise _error(404, "SOURCE_IDEA_NOT_FOUND", "来源创意不存在或无权访问")
        sources.append((idea, await get_effective_rights_chain(db, idea)))

    workspace = Collaboration(
        title=payload.title.strip(),
        description=payload.description,
        owner_id=user.id,
        status="draft",
        visibility="private",
    )
    db.add(workspace)
    await db.flush()
    db.add(CollaborationMember(
        collaboration_id=workspace.id,
        user_id=user.id,
        role="owner",
        status="accepted",
        invited_by=user.id,
        responded_at=datetime.now(timezone.utc),
    ))
    for position, (idea, rights_chain) in enumerate(sources):
        db.add(CollaborationSource(
            collaboration_id=workspace.id,
            idea_id=idea.id,
            position=position,
            rights_snapshot={
                "source_idea_id": str(idea.id),
                "source_author_id": str(idea.author_id) if idea.author_id else None,
                "license_code": idea.license_code,
                "license_text_snapshot": idea.license_text_snapshot,
                "license_version": idea.license_version,
                "allow_fork": bool(idea.allow_fork),
                "rights_chain": rights_chain,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
        ))
    await _event(db, workspace.id, user.id, "collaboration_created", {"source_count": len(sources)})
    await db.commit()
    return {
        "id": str(workspace.id),
        "title": workspace.title,
        "description": workspace.description,
        "status": workspace.status,
        "visibility": workspace.visibility,
        "owner_id": str(workspace.owner_id),
        "member_role": "owner",
        "source_count": len(sources),
    }


@router.post("/{collaboration_id}/members", status_code=201)
async def invite_member(
    collaboration_id: uuid.UUID,
    payload: CollaborationMemberInvite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace = await db.scalar(
        select(Collaboration).where(Collaboration.id == collaboration_id).with_for_update()
    )
    if workspace is None or workspace.owner_id != user.id or workspace.status != "draft":
        raise _error(404, "COLLABORATION_NOT_FOUND", "协作空间不存在或无权邀请成员")
    if payload.user_id == user.id:
        raise _error(422, "CANNOT_INVITE_SELF", "不能邀请自己")
    invitee = await db.get(User, payload.user_id)
    if invitee is None:
        raise _error(404, "USER_NOT_FOUND", "用户不存在")
    existing = await db.scalar(
        select(CollaborationMember).where(
            CollaborationMember.collaboration_id == collaboration_id,
            CollaborationMember.user_id == payload.user_id,
        ).with_for_update()
    )
    now = datetime.now(timezone.utc)
    if existing is not None:
        if existing.status in ("pending", "accepted"):
            raise _error(409, "MEMBER_ALREADY_EXISTS", "成员已被邀请或已加入")
        existing.role = payload.role
        existing.status = "pending"
        existing.invited_by = user.id
        existing.invited_at = now
        existing.responded_at = None
        existing.revoked_at = None
        member = existing
    else:
        member = CollaborationMember(
            collaboration_id=collaboration_id,
            user_id=payload.user_id,
            role=payload.role,
            status="pending",
            invited_by=user.id,
        )
        db.add(member)
    await _event(db, collaboration_id, user.id, "member_invited", {"user_id": str(payload.user_id), "role": payload.role})
    await db.commit()
    return {"invite_id": str(member.id), "user_id": str(member.user_id), "role": member.role, "status": member.status}


@router.post("/{collaboration_id}/accept")
async def accept_invitation(
    collaboration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace = await db.scalar(
        select(Collaboration).where(Collaboration.id == collaboration_id).with_for_update()
    )
    result = await db.execute(
        select(CollaborationMember).where(
            CollaborationMember.collaboration_id == collaboration_id,
            CollaborationMember.user_id == user.id,
        ).with_for_update()
    )
    member = result.scalar_one_or_none()
    if member is None or member.status != "pending":
        raise _error(404, "INVITATION_NOT_FOUND", "待处理邀请不存在")
    if workspace is None or workspace.status != "draft":
        raise _error(409, "COLLABORATION_CLOSED", "协作空间已关闭，不能接受邀请")
    member.status = "accepted"
    member.responded_at = datetime.now(timezone.utc)
    await _event(db, collaboration_id, user.id, "member_accepted", {"role": member.role})
    await db.commit()
    return {"accepted": True, "role": member.role}


@router.get("/invitations/inbox")
async def collaboration_invitation_inbox(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CollaborationMember, Collaboration.title, Collaboration.description)
        .join(Collaboration, Collaboration.id == CollaborationMember.collaboration_id)
        .where(CollaborationMember.user_id == user.id, CollaborationMember.status == "pending")
        .order_by(CollaborationMember.invited_at.desc())
        .limit(100)
    )
    return {"items": [
        {"collaboration_id": str(row.CollaborationMember.collaboration_id),
         "invite_id": str(row.CollaborationMember.id), "title": row.title,
         "description": row.description, "role": row.CollaborationMember.role,
         "invited_at": row.CollaborationMember.invited_at}
        for row in result.all()
    ]}


@router.post("/{collaboration_id}/decline")
async def decline_invitation(
    collaboration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace = await db.scalar(select(Collaboration).where(
        Collaboration.id == collaboration_id
    ).with_for_update())
    member = await db.scalar(select(CollaborationMember).where(
        CollaborationMember.collaboration_id == collaboration_id,
        CollaborationMember.user_id == user.id,
    ).with_for_update())
    if workspace is None or workspace.status != "draft" or member is None or member.status != "pending":
        raise _error(404, "INVITATION_NOT_FOUND", "待处理邀请不存在")
    member.status = "declined"
    member.responded_at = datetime.now(timezone.utc)
    await _event(db, collaboration_id, user.id, "member_declined", {"role": member.role})
    await db.commit()
    return {"declined": True}


@router.delete("/{collaboration_id}/members/{member_user_id}")
async def revoke_member(
    collaboration_id: uuid.UUID,
    member_user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace = await db.scalar(select(Collaboration).where(
        Collaboration.id == collaboration_id
    ).with_for_update())
    if workspace is None or workspace.owner_id != user.id:
        raise _error(404, "COLLABORATION_NOT_FOUND", "协作空间不存在或无权管理成员")
    if member_user_id == workspace.owner_id:
        raise _error(422, "CANNOT_REVOKE_OWNER", "不能撤销空间所有者")
    member = await db.scalar(select(CollaborationMember).where(
        CollaborationMember.collaboration_id == collaboration_id,
        CollaborationMember.user_id == member_user_id,
    ).with_for_update())
    if member is None or member.status not in ("pending", "accepted"):
        raise _error(404, "MEMBER_NOT_FOUND", "成员或邀请不存在")
    member.status = "revoked"
    member.revoked_at = datetime.now(timezone.utc)
    await _event(db, collaboration_id, user.id, "member_revoked", {"user_id": str(member_user_id)})
    await db.commit()
    return {"revoked": True}


@router.get("/{collaboration_id}")
async def get_collaboration(
    collaboration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = await _member(db, collaboration_id, user)
    workspace = await db.get(Collaboration, collaboration_id)
    source_result = await db.execute(
        select(CollaborationSource).where(
            CollaborationSource.collaboration_id == collaboration_id
        ).order_by(CollaborationSource.position)
    )
    source_items = []
    for source in source_result.scalars().all():
        idea = await db.get(Idea, source.idea_id)
        visible = bool(idea and await can_view_idea(db, idea, user.id))
        source_items.append({
            "source_ref": str(source.idea_id) if visible else f"restricted:{source.id}",
            "accessible": visible,
            # Never disclose a private source's ID, author, or license snapshot
            # merely because the viewer joined this collaboration workspace.
            **({"rights_snapshot": source.rights_snapshot} if visible else {}),
        })
    member_query = (
        select(CollaborationMember, User.username)
        .join(User, User.id == CollaborationMember.user_id)
        .where(CollaborationMember.collaboration_id == collaboration_id)
    )
    if member.role != "owner":
        member_query = member_query.where(CollaborationMember.status == "accepted")
    member_result = await db.execute(
        member_query.order_by(CollaborationMember.created_at)
    )
    members = [
        {"user_id": str(row.CollaborationMember.user_id), "username": row.username,
         "role": row.CollaborationMember.role, "status": row.CollaborationMember.status}
        for row in member_result.all()
    ]
    contribution_query = select(CollaborationContribution).where(
        CollaborationContribution.collaboration_id == collaboration_id
    )
    if member.role != "owner":
        contribution_query = contribution_query.where(CollaborationContribution.author_id == user.id)
    contribution_query = contribution_query.order_by(CollaborationContribution.created_at.desc()).limit(100)
    contributions = (await db.execute(contribution_query)).scalars().all()
    events = (await db.execute(
        select(CollaborationEvent).where(
            CollaborationEvent.collaboration_id == collaboration_id
        ).order_by(CollaborationEvent.created_at.desc()).limit(100)
    )).scalars().all()
    return {
        "id": str(workspace.id),
        "title": workspace.title,
        "description": workspace.description,
        "status": workspace.status,
        "visibility": workspace.visibility,
        "owner_id": str(workspace.owner_id),
        "member_role": member.role,
        "members": members,
        "sources": source_items,
        "contributions": [_contribution_payload(item) for item in contributions],
        "events": [{"id": str(e.id), "actor_id": str(e.actor_id) if e.actor_id else None,
                    "event_type": e.event_type, "payload": e.payload, "created_at": e.created_at}
                   for e in events],
    }


@router.post("/{collaboration_id}/contributions", status_code=201)
async def submit_contribution(
    collaboration_id: uuid.UUID,
    payload: CollaborationContributionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = await _member(db, collaboration_id, user, roles={"owner", "contributor"})
    if payload.source_idea_id is not None:
        source = await db.scalar(select(CollaborationSource).where(
            CollaborationSource.collaboration_id == collaboration_id,
            CollaborationSource.idea_id == payload.source_idea_id,
        ))
        idea = await db.get(Idea, payload.source_idea_id)
        if source is None or idea is None or not await can_view_idea(db, idea, user.id):
            raise _error(404, "SOURCE_IDEA_NOT_FOUND", "来源创意不存在或无权访问")
    workspace = await db.get(Collaboration, collaboration_id)
    if workspace is None or workspace.status != "draft":
        raise _error(409, "COLLABORATION_CLOSED", "协作空间已关闭")
    item = CollaborationContribution(
        collaboration_id=collaboration_id,
        author_id=user.id,
        source_idea_id=payload.source_idea_id,
        contribution_type=payload.contribution_type,
        content=payload.content,
        note=payload.note,
        status="submitted",
    )
    db.add(item)
    await db.flush()
    await _event(db, collaboration_id, user.id, "contribution_submitted", {"contribution_id": str(item.id)})
    await db.commit()
    return _contribution_payload(item)


@router.patch("/{collaboration_id}/contributions/{contribution_id}")
async def update_contribution(
    collaboration_id: uuid.UUID,
    contribution_id: uuid.UUID,
    payload: CollaborationContributionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _member(db, collaboration_id, user, roles={"owner", "contributor"})
    workspace = await db.get(Collaboration, collaboration_id)
    item = await db.scalar(select(CollaborationContribution).where(
        CollaborationContribution.id == contribution_id,
        CollaborationContribution.collaboration_id == collaboration_id,
    ).with_for_update())
    if workspace is None or workspace.status != "draft" or item is None or item.author_id != user.id or item.status != "submitted":
        raise _error(404, "CONTRIBUTION_NOT_FOUND", "贡献不存在或不可编辑")
    if payload.source_idea_id is not None:
        source = await db.scalar(select(CollaborationSource.id).where(
            CollaborationSource.collaboration_id == collaboration_id,
            CollaborationSource.idea_id == payload.source_idea_id,
        ))
        idea = await db.get(Idea, payload.source_idea_id)
        if source is None or idea is None or not await can_view_idea(db, idea, user.id):
            raise _error(404, "SOURCE_IDEA_NOT_FOUND", "来源创意不存在或无权访问")
    item.content = payload.content
    item.contribution_type = payload.contribution_type
    item.source_idea_id = payload.source_idea_id
    item.note = payload.note
    await _event(db, collaboration_id, user.id, "contribution_updated", {"contribution_id": str(item.id)})
    await db.commit()
    return _contribution_payload(item)


@router.delete("/{collaboration_id}/contributions/{contribution_id}")
async def withdraw_contribution(
    collaboration_id: uuid.UUID,
    contribution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _member(db, collaboration_id, user, roles={"owner", "contributor"})
    workspace = await db.get(Collaboration, collaboration_id)
    item = await db.scalar(select(CollaborationContribution).where(
        CollaborationContribution.id == contribution_id,
        CollaborationContribution.collaboration_id == collaboration_id,
    ).with_for_update())
    if workspace is None or workspace.status != "draft" or item is None or item.author_id != user.id or item.status != "submitted":
        raise _error(404, "CONTRIBUTION_NOT_FOUND", "贡献不存在或不可撤回")
    item.status = "withdrawn"
    await _event(db, collaboration_id, user.id, "contribution_withdrawn", {"contribution_id": str(item.id)})
    await db.commit()
    return {"withdrawn": True}


@router.post("/{collaboration_id}/contributions/{contribution_id}/review")
async def review_contribution(
    collaboration_id: uuid.UUID,
    contribution_id: uuid.UUID,
    payload: CollaborationContributionReview,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _member(db, collaboration_id, user, roles={"owner"})
    workspace = await db.get(Collaboration, collaboration_id)
    item = await db.scalar(select(CollaborationContribution).where(
        CollaborationContribution.id == contribution_id,
        CollaborationContribution.collaboration_id == collaboration_id,
    ).with_for_update())
    if workspace is None or workspace.status != "draft" or item is None or item.status != "submitted":
        raise _error(404, "CONTRIBUTION_NOT_FOUND", "待审核贡献不存在")
    item.status = payload.decision
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_note = payload.review_note
    await _event(db, collaboration_id, user.id, f"contribution_{payload.decision}", {"contribution_id": str(item.id)})
    await db.commit()
    return _contribution_payload(item)
