"""用户路由"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Idea, VaultItem, ForkRelation
from schemas.user import UserProfile
from services.rate_limit import limiter, DEFAULT_LIMIT
from routers.ideas import _calc_size_score

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserProfile)
@limiter.limit(DEFAULT_LIMIT)
async def get_user_profile(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "用户不存在"}},
        )

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

    forked_by_result = await db.execute(
        select(func.count()).select_from(ForkRelation)
        .join(Idea, Idea.id == ForkRelation.parent_id)
        .where(Idea.author_id == user.id)
    )
    forked_by_others = forked_by_result.scalar() or 0

    forked_others_result = await db.execute(
        select(func.count()).select_from(ForkRelation)
        .join(Idea, Idea.id == ForkRelation.child_id)
        .where(Idea.author_id == user.id)
    )
    forked_others = forked_others_result.scalar() or 0

    # 圆圈
    circles_result = await db.execute(
        select(Idea, VaultItem)
        .join(VaultItem, VaultItem.idea_id == Idea.id)
        .where(VaultItem.user_id == user.id, Idea.status != "faded")
        .order_by(VaultItem.added_at.desc())
    )
    circles = []
    for idea, vi in circles_result.all():
        circles.append({
            "id": str(idea.id),
            "color_hex": idea.color_hex,
            "size_score": _calc_size_score(idea.fork_count, idea.last_fork_at),
            "border_style": "gold-thin" if vi.is_producer else "none",
        })

    return UserProfile(
        id=str(user.id),
        username=user.username,
        bio=user.bio or "",
        stats={
            "produced": produced,
            "collected": collected,
            "forked_by_others": forked_by_others,
            "forked_others": forked_others,
        },
        circles=circles,
    )


@router.get("/me/vault")
async def my_vault_redirect(
    user: User = Depends(get_current_user),
):
    """API_SPEC 中提到的 /api/users/me/vault 重定向到 /api/vault"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/vault", status_code=307)
