"""First-class asynchronous collaboration workspaces.

Workspace membership is independent from per-Idea ACL grants: accepting a
workspace invitation never grants access to a private source Idea.
"""
from __future__ import annotations

import uuid
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import (
    User, Idea, Collaboration, CollaborationMember, CollaborationSource,
    CollaborationContribution, CollaborationEvent, IdeaContribution,
    IdeaVersion, IdeaVersionContribution, ForkRelation, Notification,
)
from schemas.collaboration import (
    CollaborationCreate, CollaborationMemberInvite,
    CollaborationContributionCreate, CollaborationContributionUpdate,
    CollaborationContributionReview, CollaborationPublish,
)
from services.idea_access import (
    can_view_idea, get_effective_rights_chain, can_derive_from_idea,
    requires_custom_license_confirmation, build_derivation_snapshot,
)
from services.audit_service import audit_content, write_audit_log
from services.color_pool import random_color
from services.cache import cache, key_idea_detail
from services.rate_limit import limiter, DEFAULT_LIMIT
from services.notification_preferences import add_notification_if_enabled

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


async def _draft_member(
    db: AsyncSession, collaboration_id: uuid.UUID, user: User, *, roles=None
):
    """Lock workspace first, then membership, matching publish/revoke lock order."""
    workspace = await db.scalar(
        select(Collaboration).where(
            Collaboration.id == collaboration_id
        ).with_for_update()
    )
    if workspace is None:
        raise _error(404, "COLLABORATION_NOT_FOUND", "协作空间不存在或无权访问")
    if workspace.status != "draft":
        raise _error(409, "COLLABORATION_CLOSED", "协作空间已完成发布或归档")
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
    return workspace, member


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
    published_idea = (
        await db.get(Idea, workspace.published_idea_id)
        if workspace.published_idea_id else None
    )
    published_result = None
    if published_idea is not None:
        published_result = {
            "content": published_idea.content,
            "visibility": published_idea.visibility,
            "license_code": published_idea.license_code,
            "license_text_snapshot": published_idea.license_text_snapshot,
            "allow_fork": published_idea.allow_fork,
            "published_at": published_idea.published_at,
            # Private result IDs are only exposed to the workspace owner.
            "idea_id": (
                str(published_idea.id)
                if published_idea.visibility == "public" or workspace.owner_id == user.id
                else None
            ),
        }
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


@router.get("/{collaboration_id}/members/search")
@limiter.limit(DEFAULT_LIMIT)
async def search_collaboration_members(
    request: Request,
    collaboration_id: UUID,
    q: str = Query(..., min_length=2, max_length=80),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Owner-only username search; returns only invite candidates and minimal fields."""
    query = q.strip()
    if len(query) < 2:
        raise _error(422, "SEARCH_QUERY_TOO_SHORT", "搜索词至少需要 2 个字符")
    workspace = await db.get(Collaboration, collaboration_id)
    if workspace is None or workspace.owner_id != user.id or workspace.status != "draft":
        raise _error(404, "COLLABORATION_NOT_FOUND", "协作空间不存在或无权邀请成员")

    existing_members = select(CollaborationMember.user_id).where(
        CollaborationMember.collaboration_id == collaboration_id,
        CollaborationMember.status.in_(["pending", "accepted"]),
    )
    result = await db.execute(
        select(User.id, User.username)
        .where(
            User.id != user.id,
            User.username.ilike(f"%{query}%"),
            ~User.id.in_(existing_members),
        )
        .order_by(User.username.asc())
        .limit(20)
    )
    return {
        "items": [
            {"user_id": str(row.id), "username": row.username}
            for row in result.all()
        ]
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
    await add_notification_if_enabled(
        db,
        user_id=payload.user_id,
        notification_type="collab_invited",
        content=f"{user.username} 邀请你加入协作空间：{workspace.title}",
        actor_id=user.id,
        collaboration_id=collaboration_id,
    )
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


@router.delete("/{collaboration_id}/leave")
async def leave_collaboration(
    collaboration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Allow an accepted non-owner member to leave; serialize with workspace writes."""
    workspace = await db.scalar(
        select(Collaboration).where(
            Collaboration.id == collaboration_id
        ).with_for_update()
    )
    if workspace is None:
        raise _error(404, "COLLABORATION_NOT_FOUND", "协作空间不存在或无权访问")
    if workspace.owner_id == user.id:
        raise _error(422, "OWNER_CANNOT_LEAVE", "空间所有者不能直接离开，请先归档空间")
    member = await db.scalar(
        select(CollaborationMember).where(
            CollaborationMember.collaboration_id == collaboration_id,
            CollaborationMember.user_id == user.id,
        ).with_for_update()
    )
    if member is None or member.status != "accepted":
        raise _error(404, "MEMBERSHIP_NOT_FOUND", "有效成员关系不存在")
    member.status = "left"
    member.responded_at = datetime.now(timezone.utc)
    member.revoked_at = datetime.now(timezone.utc)
    await _event(db, collaboration_id, user.id, "member_left", {"role": member.role})
    await db.commit()
    return {"left": True}


@router.post("/{collaboration_id}/archive")
async def archive_collaboration(
    collaboration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Owner archives a workspace; archived workspaces become read-only."""
    workspace = await db.scalar(
        select(Collaboration).where(
            Collaboration.id == collaboration_id
        ).with_for_update()
    )
    if workspace is None or workspace.owner_id != user.id:
        raise _error(404, "COLLABORATION_NOT_FOUND", "协作空间不存在或无权归档")
    if workspace.status == "archived":
        return {"archived": True, "status": "archived"}
    workspace.status = "archived"
    await _event(db, collaboration_id, user.id, "collaboration_archived")
    await db.commit()
    return {"archived": True, "status": workspace.status}


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
        .where(
            CollaborationMember.collaboration_id == collaboration_id,
            CollaborationMember.status.in_(["accepted", "pending"]),
        )
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
    event_query = select(CollaborationEvent).where(
        CollaborationEvent.collaboration_id == collaboration_id
    )
    if member.role != "owner":
        # A contributor must not infer other members' proposal IDs or invitation targets.
        event_query = event_query.where(CollaborationEvent.actor_id == user.id)
    events = (await db.execute(
        event_query.order_by(CollaborationEvent.created_at.desc()).limit(100)
    )).scalars().all()
    published_idea = (
        await db.get(Idea, workspace.published_idea_id)
        if workspace.published_idea_id else None
    )
    published_result = None
    if published_idea is not None:
        published_result = {
            "content": published_idea.content,
            "visibility": published_idea.visibility,
            "license_code": published_idea.license_code,
            "license_text_snapshot": published_idea.license_text_snapshot,
            "allow_fork": published_idea.allow_fork,
            "published_at": published_idea.published_at,
            "idea_id": (
                str(published_idea.id)
                if published_idea.visibility == "public" or workspace.owner_id == user.id
                else None
            ),
        }
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
        "published_result": published_result,
    }


@router.post("/{collaboration_id}/contributions", status_code=201)
async def submit_contribution(
    collaboration_id: uuid.UUID,
    payload: CollaborationContributionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace, member = await _draft_member(db, collaboration_id, user, roles={"owner", "contributor"})
    if payload.source_idea_id is not None:
        source = await db.scalar(select(CollaborationSource).where(
            CollaborationSource.collaboration_id == collaboration_id,
            CollaborationSource.idea_id == payload.source_idea_id,
        ))
        idea = await db.get(Idea, payload.source_idea_id)
        if source is None or idea is None or not await can_view_idea(db, idea, user.id):
            raise _error(404, "SOURCE_IDEA_NOT_FOUND", "来源创意不存在或无权访问")
    passed, reason = await audit_content(db, payload.content)
    if not passed:
        raise _error(403, "AUDIT_FAILED", reason or "贡献内容审核不通过")
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
    workspace, member = await _draft_member(db, collaboration_id, user, roles={"owner", "contributor"})
    item = await db.scalar(select(CollaborationContribution).where(
        CollaborationContribution.id == contribution_id,
        CollaborationContribution.collaboration_id == collaboration_id,
    ).with_for_update())
    if item is None or item.author_id != user.id or item.status != "submitted":
        raise _error(404, "CONTRIBUTION_NOT_FOUND", "贡献不存在或不可编辑")
    if payload.source_idea_id is not None:
        source = await db.scalar(select(CollaborationSource.id).where(
            CollaborationSource.collaboration_id == collaboration_id,
            CollaborationSource.idea_id == payload.source_idea_id,
        ))
        idea = await db.get(Idea, payload.source_idea_id)
        if source is None or idea is None or not await can_view_idea(db, idea, user.id):
            raise _error(404, "SOURCE_IDEA_NOT_FOUND", "来源创意不存在或无权访问")
    passed, reason = await audit_content(db, payload.content)
    if not passed:
        raise _error(403, "AUDIT_FAILED", reason or "贡献内容审核不通过")
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
    workspace, member = await _draft_member(db, collaboration_id, user, roles={"owner", "contributor"})
    item = await db.scalar(select(CollaborationContribution).where(
        CollaborationContribution.id == contribution_id,
        CollaborationContribution.collaboration_id == collaboration_id,
    ).with_for_update())
    if item is None or item.author_id != user.id or item.status != "submitted":
        raise _error(404, "CONTRIBUTION_NOT_FOUND", "贡献不存在或不可撤回")
    item.status = "withdrawn"
    await _event(db, collaboration_id, user.id, "contribution_withdrawn", {"contribution_id": str(item.id)})
    await db.commit()
    return {"withdrawn": True}



@router.post("/{collaboration_id}/publish", status_code=201)
async def publish_collaboration(
    collaboration_id: uuid.UUID,
    payload: CollaborationPublish,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Atomically publish the owner's accepted workspace result as a new Idea.

    All source Ideas must currently be public and derivable. Source rows are locked
    in deterministic UUID order so publication cannot race source withdrawal.
    """
    workspace = await db.scalar(
        select(Collaboration).where(
            Collaboration.id == collaboration_id
        ).with_for_update()
    )
    if workspace is None or workspace.owner_id != user.id:
        raise _error(404, "COLLABORATION_NOT_FOUND", "协作空间不存在或无权发布")
    if workspace.status != "draft":
        raise _error(409, "COLLABORATION_ALREADY_PUBLISHED", "协作空间已完成发布")

    source_result = await db.execute(
        select(CollaborationSource).where(
            CollaborationSource.collaboration_id == collaboration_id
        ).order_by(CollaborationSource.position).with_for_update()
    )
    source_rows = source_result.scalars().all()
    if not source_rows:
        raise _error(422, "COLLABORATION_SOURCES_REQUIRED", "协作空间必须至少关联一个来源创意")
    source_ids = [row.idea_id for row in source_rows]

    locked_result = await db.execute(
        select(Idea).where(Idea.id.in_(source_ids)).order_by(Idea.id).with_for_update()
    )
    locked_sources = {idea.id: idea for idea in locked_result.scalars().all()}
    if len(locked_sources) != len(source_ids):
        raise _error(404, "SOURCE_IDEA_NOT_FOUND", "来源创意不存在")

    sources = [locked_sources[row.idea_id] for row in source_rows]
    for source in sources:
        if not await can_derive_from_idea(db, source, user.id):
            raise _error(
                422, "SOURCE_LICENSE_BLOCKS_DERIVATION",
                "所有来源及其祖先都必须允许改编，且来源必须保持公开有效",
            )

    custom_required = await requires_custom_license_confirmation(db, sources)
    if custom_required and not payload.confirm_custom_licenses:
        raise _error(
            422, "CUSTOM_LICENSE_CONFIRMATION_REQUIRED",
            "来源或祖先包含自定义授权，必须明确确认已阅读并接受全部条款",
        )
    if payload.visibility == "public" and not payload.confirm_terms:
        raise _error(400, "TERMS_NOT_CONFIRMED", "公开发布必须确认最终授权条款")
    if payload.license_code == "custom" and not (payload.license_custom_text or "").strip():
        raise _error(422, "LICENSE_TEXT_REQUIRED", "自定义授权必须填写授权说明")
    if payload.allow_fork and payload.license_code not in ("attribution_adaptation", "custom"):
        raise _error(422, "LICENSE_DERIVATIVE_MISMATCH", "当前授权不允许开启继续衍生")
    if payload.allow_fork and payload.visibility != "public":
        raise _error(422, "PRIVATE_DERIVATION_DISABLED", "私有草稿不能开启公开衍生权限")
    if payload.allow_fork:
        for source in sources:
            chain = await get_effective_rights_chain(db, source)
            if not chain or any(
                item.get("allow_fork") is not True
                or item.get("license_code") not in ("attribution_adaptation", "custom")
                for item in chain
            ):
                raise _error(
                    422, "INHERITED_LICENSE_BLOCKS_DERIVATION",
                    "任一上游授权不允许继续衍生，不能通过协作发布扩大权限",
                )

    selected_ids = payload.accepted_contribution_ids
    if len(selected_ids) != len(set(selected_ids)):
        raise _error(422, "DUPLICATE_CONTRIBUTION", "贡献不能重复选择")
    if selected_ids:
        contribution_result = await db.execute(
            select(CollaborationContribution).where(
                CollaborationContribution.collaboration_id == collaboration_id,
                CollaborationContribution.id.in_(selected_ids),
                CollaborationContribution.status == "accepted",
            ).order_by(CollaborationContribution.id).with_for_update()
        )
        accepted = contribution_result.scalars().all()
        if len(accepted) != len(selected_ids):
            raise _error(409, "CONTRIBUTION_NOT_ACCEPTED", "只能选择当前协作空间中已采纳的贡献")
    else:
        accepted = []

    passed, reason = await audit_content(db, payload.content)
    if not passed:
        raise _error(403, "AUDIT_FAILED", reason or "内容审核不通过")

    now = datetime.now(timezone.utc)
    is_public = payload.visibility == "public"
    idea = Idea(
        content=payload.content,
        color_hex=random_color(),
        source="merge" if len(sources) > 1 else "fork",
        author_id=user.id,
        border_style="gold-thin",
        publication_status="published" if is_public else "draft",
        visibility=payload.visibility,
        license_code=payload.license_code,
        license_text_snapshot=payload.license_custom_text,
        license_version=payload.license_version,
        allow_fork=bool(is_public and payload.allow_fork),
        is_forkable=bool(is_public and payload.allow_fork),
        published_at=now if is_public else None,
        legacy_license_review_status="not_required",
    )
    db.add(idea)
    await db.flush()

    version = IdeaVersion(
        idea_id=idea.id,
        version_number=1,
        content_snapshot=payload.content,
        change_summary=payload.change_summary,
        status="published" if is_public else "draft",
        created_by=user.id,
        published_by=user.id if is_public else None,
        published_at=now if is_public else None,
    )
    db.add(version)
    await db.flush()

    for contribution in accepted:
        author_name = await db.scalar(
            select(User.username).where(User.id == contribution.author_id)
        ) or "匿名"
        bridge = IdeaContribution(
            idea_id=idea.id,
            author_id=contribution.author_id,
            content=contribution.content,
            note=contribution.note,
            status="accepted",
            reviewed_by=user.id,
            reviewed_at=now,
            review_note="经协作空间审核并纳入发布版本",
            source_collaboration_contribution_id=contribution.id,
        )
        db.add(bridge)
        await db.flush()
        db.add(IdeaVersionContribution(
            version_id=version.id,
            contribution_id=bridge.id,
            author_id_snapshot=contribution.author_id,
            author_name_snapshot=author_name,
            content_snapshot=contribution.content,
        ))

    relation_type = "merge" if len(sources) > 1 else "fork"
    for source in sources:
        snapshot = await build_derivation_snapshot(
            db,
            source,
            custom_license_acknowledged=payload.confirm_custom_licenses,
            acknowledged_by=user.id,
        )
        db.add(ForkRelation(
            child_id=idea.id,
            parent_id=source.id,
            relation_type=relation_type,
            angle="collaboration",
            license_snapshot=snapshot,
        ))
        source.fork_count = (source.fork_count or 0) + 1
        source.last_fork_at = now

    workspace.status = "published"
    workspace.visibility = payload.visibility
    workspace.published_idea_id = idea.id
    workspace.published_at = now
    await write_audit_log(db, idea.id, payload.content, True, "collaboration publication")
    await _event(
        db, collaboration_id, user.id, "collaboration_published",
        {"visibility": payload.visibility, "source_count": len(sources)},
    )

    member_result = await db.execute(
        select(CollaborationMember).where(
            CollaborationMember.collaboration_id == collaboration_id,
            CollaborationMember.status == "accepted",
            CollaborationMember.user_id != user.id,
        )
    )
    for member in member_result.scalars().all():
        await add_notification_if_enabled(
            db,
            user_id=member.user_id,
            notification_type="collab_published",
            content="协作空间成果已完成发布",
            idea_id=idea.id if is_public else None,
            actor_id=user.id,
            collaboration_id=collaboration_id,
        )

    await db.commit()
    if is_public:
        await cache.delete_pattern("explore:v3:*")
    await cache.delete(key_idea_detail(str(idea.id)))
    return {
        "collaboration_id": str(workspace.id),
        "idea_id": str(idea.id),
        "version_id": str(version.id),
        "version_number": 1,
        "publication_status": idea.publication_status,
        "visibility": idea.visibility,
        "source_idea_ids": [str(source.id) for source in sources],
        "attribution_count": len(accepted),
    }

@router.post("/{collaboration_id}/contributions/{contribution_id}/review")
async def review_contribution(
    collaboration_id: uuid.UUID,
    contribution_id: uuid.UUID,
    payload: CollaborationContributionReview,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace, member = await _draft_member(db, collaboration_id, user, roles={"owner"})
    item = await db.scalar(select(CollaborationContribution).where(
        CollaborationContribution.id == contribution_id,
        CollaborationContribution.collaboration_id == collaboration_id,
    ).with_for_update())
    if item is None or item.status != "submitted":
        raise _error(404, "CONTRIBUTION_NOT_FOUND", "待审核贡献不存在")
    item.status = payload.decision
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_note = payload.review_note
    await _event(db, collaboration_id, user.id, f"contribution_{payload.decision}", {"contribution_id": str(item.id)})
    if item.author_id != user.id:
        await add_notification_if_enabled(
            db,
            user_id=item.author_id,
            notification_type="collab_reviewed",
            content=f"你在协作空间「{workspace.title}」中的贡献已{ '采纳' if payload.decision == 'accepted' else '拒绝' }",
            actor_id=user.id,
            collaboration_id=collaboration_id,
        )
    await db.commit()
    return _contribution_payload(item)
