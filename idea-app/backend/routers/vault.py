"""仓库路由"""
import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, delete, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Idea, VaultItem, ForkRelation, IdeaAccessGrant
from schemas.vault import (
    VaultStats, VaultCircle, VaultResponse,
    CollectResponse, RemoveResponse,
)
from services.cache import cache, key_user_vault
from services.rate_limit import limiter, DEFAULT_LIMIT
from routers.ideas import _calc_size_score
from services.idea_access import can_view_idea

router = APIRouter(prefix="/vault", tags=["vault"])


@router.get("", response_model=VaultResponse)
@limiter.limit(DEFAULT_LIMIT)
async def get_vault(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 统计
    produced_result = await db.execute(
        select(func.count()).select_from(VaultItem).where(
            VaultItem.user_id == user.id, VaultItem.is_producer == True
        )
    )
    produced = produced_result.scalar() or 0

    collected_result = await db.execute(
        select(func.count()).select_from(VaultItem).where(
            VaultItem.user_id == user.id, VaultItem.is_producer == False
        )
    )
    collected = collected_result.scalar() or 0

    # 被别人 fork 的总数
    forked_by_result = await db.execute(
        select(func.count()).select_from(ForkRelation)
        .join(Idea, Idea.id == ForkRelation.parent_id)
        .where(Idea.author_id == user.id)
    )
    forked_by_others = forked_by_result.scalar() or 0

    # 圆圈列表
    result = await db.execute(
        select(Idea, VaultItem)
        .join(VaultItem, VaultItem.idea_id == Idea.id)
        .where(
            VaultItem.user_id == user.id,
            Idea.status != "faded",
            or_(
                Idea.author_id == user.id,
                and_(Idea.publication_status == "published", Idea.visibility == "public", Idea.status == "active"),
                select(IdeaAccessGrant.id).where(
                    IdeaAccessGrant.idea_id == Idea.id,
                    IdeaAccessGrant.user_id == user.id,
                    IdeaAccessGrant.status == "accepted",
                ).exists(),
            ),
        )
        .order_by(VaultItem.last_touch_at.desc())
        .limit(limit).offset(offset)
    )
    circles = []
    for idea, vi in result.all():
        circles.append(VaultCircle(
            id=str(idea.id),
            color_hex=idea.color_hex,
            size_score=_calc_size_score(idea.fork_count, idea.last_fork_at),
            border_style="gold-thin" if vi.is_producer else "none",
            status=idea.status,
            last_touch_at=vi.last_touch_at,
        ))

    return VaultResponse(
        stats=VaultStats(produced=produced, collected=collected, forked_by_others=forked_by_others),
        circles=circles,
        has_more=len(circles) >= limit,
    )


@router.delete("/{idea_id}", response_model=RemoveResponse)
@limiter.limit(DEFAULT_LIMIT)
async def remove_from_vault(
    request: Request,
    idea_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(VaultItem).where(
            VaultItem.user_id == user.id, VaultItem.idea_id == idea_id
        )
    )
    vault_item = result.scalar_one_or_none()
    if vault_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "点子不在仓库中"}},
        )

    await db.delete(vault_item)

    # Removing a VaultItem is a personal collection action, never an Idea deletion.
    await db.commit()
    await cache.delete(key_user_vault(str(user.id)))
    return RemoveResponse(removed=True, idea_id=str(idea_id))


@router.post("/{idea_id}/collect", response_model=CollectResponse, status_code=201)
@limiter.limit(DEFAULT_LIMIT)
async def collect_idea(
    request: Request,
    idea_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 验证点子存在
    idea_result = await db.execute(select(Idea).where(Idea.id == idea_id))
    idea = idea_result.scalar_one_or_none()
    if idea is None or not await can_view_idea(db, idea, user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}},
        )

    # 检查是否已在仓库
    existing = await db.execute(
        select(VaultItem).where(
            VaultItem.user_id == user.id, VaultItem.idea_id == idea_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_EXISTS", "message": "已在仓库中"}},
        )

    vault_item = VaultItem(
        user_id=user.id,
        idea_id=idea_id,
        is_producer=False,
    )
    db.add(vault_item)
    await db.commit()
    await cache.delete(key_user_vault(str(user.id)))
    return CollectResponse(collected=True, idea_id=str(idea_id))
