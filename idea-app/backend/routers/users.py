"""用户路由"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Idea, VaultItem, ForkRelation, IdeaVersion, IdeaVersionContribution
from schemas.user import UserProfile
from services.rate_limit import limiter, DEFAULT_LIMIT
from routers.ideas import _calc_size_score

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/search")
@limiter.limit(DEFAULT_LIMIT)
async def search_public_creators(
    request: Request,
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Search public creator profiles; ranking uses only public Ideas and attributions."""
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="搜索词至少需要 2 个字符")

    public_idea_count = (
        select(func.count())
        .select_from(Idea)
        .where(
            Idea.author_id == User.id,
            Idea.status == "active",
            Idea.publication_status == "published",
            Idea.visibility == "public",
        )
        .correlate(User)
        .scalar_subquery()
    )
    public_contribution_count = (
        select(func.count())
        .select_from(IdeaVersionContribution)
        .join(IdeaVersion, IdeaVersion.id == IdeaVersionContribution.version_id)
        .join(Idea, Idea.id == IdeaVersion.idea_id)
        .where(
            IdeaVersionContribution.author_id_snapshot == User.id,
            IdeaVersion.status == "published",
            Idea.status == "active",
            Idea.publication_status == "published",
            Idea.visibility == "public",
        )
        .correlate(User)
        .scalar_subquery()
    )
    result = await db.execute(
        select(
            User.id,
            User.username,
            User.bio,
            public_idea_count.label("public_idea_count"),
            public_contribution_count.label("public_contribution_count"),
        )
        .where(
            User.username.ilike(f"%{query}%"),
            or_(public_idea_count > 0, public_contribution_count > 0),
        )
        .order_by(
            public_contribution_count.desc(),
            public_idea_count.desc(),
            User.username.asc(),
        )
        .offset(offset)
        .limit(limit + 1)
    )
    rows = result.all()
    has_more = len(rows) > limit
    items = rows[:limit]
    return {
        "items": [
            {
                "id": str(row.id),
                "username": row.username,
                "bio": row.bio or "",
                "public_idea_count": int(row.public_idea_count or 0),
                "public_contribution_count": int(row.public_contribution_count or 0),
            }
            for row in items
        ],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


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
        select(func.count()).select_from(VaultItem)
        .join(Idea, Idea.id == VaultItem.idea_id)
        .where(
            VaultItem.user_id == user.id,
            VaultItem.is_producer == True,
            Idea.publication_status == "published",
            Idea.visibility == "public",
            Idea.status == "active",
        )
    )
    produced = produced_result.scalar() or 0

    collected_result = await db.execute(
        select(func.count()).select_from(VaultItem)
        .join(Idea, Idea.id == VaultItem.idea_id)
        .where(
            VaultItem.user_id == user.id,
            VaultItem.is_producer == False,
            Idea.publication_status == "published",
            Idea.visibility == "public",
            Idea.status == "active",
        )
    )
    collected = collected_result.scalar() or 0

    forked_by_result = await db.execute(
        select(func.count()).select_from(ForkRelation)
        .join(Idea, Idea.id == ForkRelation.parent_id)
        .where(
            Idea.author_id == user.id,
            Idea.publication_status == "published",
            Idea.visibility == "public",
            Idea.status == "active",
        )
    )
    forked_by_others = forked_by_result.scalar() or 0

    forked_others_result = await db.execute(
        select(func.count()).select_from(ForkRelation)
        .join(Idea, Idea.id == ForkRelation.child_id)
        .where(
            Idea.author_id == user.id,
            Idea.publication_status == "published",
            Idea.visibility == "public",
            Idea.status == "active",
        )
    )
    forked_others = forked_others_result.scalar() or 0

    # 圆圈
    circles_result = await db.execute(
        select(Idea, VaultItem)
        .join(VaultItem, VaultItem.idea_id == Idea.id)
        .where(
            VaultItem.user_id == user.id,
            Idea.status == "active",
            Idea.publication_status == "published",
            Idea.visibility == "public",
        )
        .order_by(VaultItem.created_at.desc())
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


@router.get("/{user_id}/contributions")
@limiter.limit(DEFAULT_LIMIT)
async def get_user_contributions(
    request: Request,
    user_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """公开展示用户已被正式发布版本采纳的贡献；私有创意与草稿一律不暴露。"""
    user_result = await db.execute(select(User.id).where(User.id == user_id))
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "用户不存在"}},
        )

    public_filters = (
        IdeaVersionContribution.author_id_snapshot == user_id,
        IdeaVersion.status == "published",
        Idea.publication_status == "published",
        Idea.visibility == "public",
        Idea.status == "active",
    )
    count_result = await db.execute(
        select(func.count())
        .select_from(IdeaVersionContribution)
        .join(IdeaVersion, IdeaVersion.id == IdeaVersionContribution.version_id)
        .join(Idea, Idea.id == IdeaVersion.idea_id)
        .where(*public_filters)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(IdeaVersionContribution, IdeaVersion, Idea)
        .join(IdeaVersion, IdeaVersion.id == IdeaVersionContribution.version_id)
        .join(Idea, Idea.id == IdeaVersion.idea_id)
        .where(*public_filters)
        .order_by(IdeaVersion.published_at.desc(), IdeaVersion.version_number.desc())
        .offset(offset)
        .limit(limit)
    )
    items = []
    for attribution, version, idea in result.all():
        items.append({
            "id": str(attribution.id),
            "idea_id": str(idea.id),
            "idea_content": version.content_snapshot,
            "version_id": str(version.id),
            "version_number": version.version_number,
            "published_at": version.published_at.isoformat() if version.published_at else None,
            "change_summary": version.change_summary,
            "contribution_content": attribution.content_snapshot,
            "author_name": attribution.author_name_snapshot,
        })

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@router.get("/me/vault")
async def my_vault_redirect(
    user: User = Depends(get_current_user),
):
    """API_SPEC 中提到的 /api/users/me/vault 重定向到 /api/vault"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/vault", status_code=307)
