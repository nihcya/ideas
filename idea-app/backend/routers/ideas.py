"""点子路由：探索/详情/创建/Fork"""
from datetime import datetime, timedelta, timezone
from typing import Literal
import math
import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, text, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user, get_optional_user
from models import User, Idea, VaultItem, ForkRelation, Notification, IdeaAccessGrant, IdeaContribution, IdeaVersion, IdeaVersionContribution
from schemas.idea import (
    IdeaCreate, IdeaForkRequest, CircleData, ExploreResponse,
    LineageNode, Lineage, IdeaDetail, IdeaResponse, ForkResponse,
    IdeaPublishRequest, IdeaInviteRequest,
    IdeaContributionCreate, IdeaContributionUpdate, IdeaContributionReview,
)
from schemas.common import SuccessResponse
from services.color_pool import random_color
from services.audit_service import audit_content, write_audit_log
from services.cache import cache, key_idea_detail, key_user_vault
from services.rate_limit import limiter, CREATE_LIMIT
from services.idea_access import (can_view_idea, can_derive_from_idea, build_derivation_snapshot, requires_custom_license_confirmation, get_inherited_rights_chain)
from services.notification_preferences import add_notification_if_enabled

router = APIRouter(prefix="/ideas", tags=["ideas"])


# ============================================================
# 圆圈大小计算：size_score = f(fork_count, 近期衰减)
# ============================================================

def _calc_size_score(fork_count: int, last_fork_at: datetime | None) -> float:
    """0-1 之间。fork_count 越多大，近期 fork 衰减。"""
    # 基础大小：log(fork_count+1) 归一化
    base = math.log1p(fork_count) / math.log1p(50)  # 50 fork 时接近 1
    base = min(max(base, 0.3), 1.0)  # 下限 0.3，上限 1.0

    # 近期衰减：30天前 fork 衰减到 0.7
    if last_fork_at:
        now = datetime.now(timezone.utc)
        days_ago = (now - last_fork_at).days if last_fork_at.tzinfo else (now.replace(tzinfo=None) - last_fork_at).days
        if days_ago > 30:
            decay = max(0.7, 1.0 - (days_ago - 30) * 0.005)
            base = base * decay
    return round(base, 3)


# ============================================================
# GET /ideas/explore — 主页探索
# ============================================================

@router.get("/explore", response_model=ExploreResponse)
async def explore(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, min_length=2, max_length=80),
    sort: Literal["recommended", "latest", "forked"] = Query("recommended"),
    license_code: str | None = Query(None, max_length=32),
    allow_fork: bool | None = Query(None),
    source: str | None = Query(None, max_length=24),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    query_text = q.strip() if q is not None else None
    if q is not None and (query_text is None or len(query_text) < 2):
        raise HTTPException(status_code=422, detail="搜索词至少需要 2 个字符")

    filters = [
        Idea.status == "active",
        Idea.publication_status == "published",
        Idea.visibility == "public",
    ]
    if query_text:
        filters.append(Idea.content.ilike(f"%{query_text}%"))
    if license_code:
        filters.append(Idea.license_code == license_code)
    if allow_fork is not None:
        filters.append(Idea.allow_fork == allow_fork)
    if source:
        filters.append(Idea.source == source)

    cache_material = "|".join([
        str(user.id) if user else "anon",
        str(limit), str(offset), sort, query_text or "",
        license_code or "", str(allow_fork), source or "",
    ])
    cache_suffix = hashlib.sha256(cache_material.encode("utf-8")).hexdigest()[:20]
    cache_key = f"explore:v3:{cache_suffix}"
    cached = await cache.get(cache_key)
    if cached:
        return ExploreResponse(**cached)

    lock_key = f"explore:lock:v3:{cache_suffix}"
    lock_token = await cache.acquire_lock(lock_key, ttl=10)
    if lock_token is None:
        waited = await cache.wait_for_cache(cache_key, retries=5, interval=0.05)
        if waited is not None:
            return ExploreResponse(**waited)

    try:
        cached = await cache.get(cache_key)
        if cached:
            return ExploreResponse(**cached)

        if sort == "latest":
            result = await db.execute(
                select(Idea).where(*filters)
                .order_by(Idea.created_at.desc(), Idea.id.desc())
                .offset(offset).limit(limit + 1)
            )
            page_ideas = result.scalars().all()
            has_more = len(page_ideas) > limit
            all_ideas = page_ideas[:limit]
        elif sort == "forked":
            result = await db.execute(
                select(Idea).where(*filters)
                .order_by(Idea.fork_count.desc(), Idea.created_at.desc(), Idea.id.desc())
                .offset(offset).limit(limit + 1)
            )
            page_ideas = result.scalars().all()
            has_more = len(page_ideas) > limit
            all_ideas = page_ideas[:limit]
        else:
            # Stable daily shuffle: 10% recent hot Ideas are interleaved with
            # 90% deterministic random Ideas, so pagination does not repeat.
            pool_result = await db.execute(
                select(Idea).where(*filters)
                .order_by(Idea.created_at.desc())
                .limit(5000)
            )
            pool = pool_result.scalars().all()
            now = datetime.now(timezone.utc)
            thirty_days_ago = now - timedelta(days=30)
            def _normalized_last_fork(idea):
                value = idea.last_fork_at
                if value is None:
                    return datetime.min.replace(tzinfo=timezone.utc)
                return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

            hot = sorted(
                [
                    idea for idea in pool
                    if idea.last_fork_at and _normalized_last_fork(idea) >= thirty_days_ago
                ],
                key=lambda idea: (idea.fork_count or 0, _normalized_last_fork(idea)),
                reverse=True,
            )
            hot_ids = {idea.id for idea in hot}
            day_seed = now.date().isoformat()
            random_pool = [idea for idea in pool if idea.id not in hot_ids]
            random_pool.sort(
                key=lambda idea: hashlib.sha256(f"{day_seed}:{idea.id}".encode("utf-8")).digest()
            )
            ordered = []
            hot_index = 0
            random_index = 0
            while hot_index < len(hot) or random_index < len(random_pool):
                if hot_index < len(hot) and (len(ordered) % 10 == 0 or random_index >= len(random_pool)):
                    ordered.append(hot[hot_index])
                    hot_index += 1
                elif random_index < len(random_pool):
                    ordered.append(random_pool[random_index])
                    random_index += 1
                else:
                    break
            all_ideas = ordered[offset:offset + limit]
            has_more = offset + limit < len(ordered)

        user_vault_ids: set[str] = set()
        if user:
            vault_result = await db.execute(
                select(VaultItem.idea_id).where(VaultItem.user_id == user.id)
            )
            user_vault_ids = {str(row[0]) for row in vault_result.all()}

        circles = [
            CircleData(
                id=str(idea.id),
                color_hex=idea.color_hex,
                size_score=_calc_size_score(idea.fork_count, idea.last_fork_at),
                is_own=str(idea.id) in user_vault_ids,
                fork_count=idea.fork_count,
                border_style='gold-thin' if (user and idea.author_id == user.id) else None,
            )
            for idea in all_ideas
        ]
        response = ExploreResponse(circles=circles, has_more=has_more)
        await cache.set(cache_key, response.model_dump(mode="json"), ttl=300)
        return response
    finally:
        if lock_token is not None:
            await cache.release_lock(lock_key, lock_token)


# ============================================================
# GET /ideas/{id} — 点子详情
# ============================================================

@router.get("/search")
async def search_ideas(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Search only Ideas the current viewer is allowed to read."""
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="搜索词至少需要 2 个字符")
    viewer_id = user.id if user else None
    visible_conditions = [
        and_(
            Idea.status == "active",
            Idea.publication_status == "published",
            Idea.visibility == "public",
        )
    ]
    if viewer_id is not None:
        visible_conditions.append(Idea.author_id == viewer_id)
        visible_conditions.append(
            Idea.id.in_(
                select(IdeaAccessGrant.idea_id).where(
                    IdeaAccessGrant.user_id == viewer_id,
                    IdeaAccessGrant.status == "accepted",
                )
            )
        )
    result = await db.execute(
        select(Idea, User.username)
        .outerjoin(User, User.id == Idea.author_id)
        .where(
            Idea.status != "rejected",
            Idea.content.ilike(f"%{query}%"),
            or_(*visible_conditions),
        )
        .order_by(Idea.created_at.desc())
        .limit(limit)
    )
    items = [
        {
            "id": str(idea.id),
            "content": idea.content,
            "title": idea.content[:60],
            "color_hex": idea.color_hex,
            "author": author or "匿名",
            "visibility": idea.visibility,
            "publication_status": idea.publication_status,
            "source": idea.source,
            "fork_count": idea.fork_count,
            "created_at": idea.created_at,
        }
        for idea, author in result.all()
    ]
    return {"items": items, "count": len(items)}


@router.get("/{idea_id}", response_model=IdeaDetail)
async def get_idea_detail(
    idea_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    result = await db.execute(select(Idea).where(Idea.id == idea_id))
    idea = result.scalar_one_or_none()
    if (
        idea is None
        or idea.status == "rejected"
        or not await can_view_idea(db, idea, user.id if user else None)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}},
        )

    # 作者信息
    author: dict = {"id": "", "username": "", "bio": ""}
    if idea.author_id:
        author_result = await db.execute(select(User).where(User.id == idea.author_id))
        author_user = author_result.scalar_one_or_none()
        if author_user:
            author = {
                "id": str(author_user.id),
                "username": author_user.username,
                "bio": author_user.bio or "",
            }

    # 是否在仓库
    is_in_vault = False
    if user:
        vault_result = await db.execute(
            select(VaultItem).where(
                VaultItem.user_id == user.id,
                VaultItem.idea_id == idea.id,
            )
        )
        # 注意:result 只能消费一次,scalar_one_or_none 后不能再调用 scalar_one
        vault_item = vault_result.scalar_one_or_none()
        is_in_vault = vault_item is not None
        # 触碰仓库（更新 last_touch_at）
        if is_in_vault:
            vault_item.last_touch_at = datetime.now(timezone.utc)
            await db.commit()

    # 谱系图：父节点
    parents_result = await db.execute(
        select(
            Idea, User, ForkRelation.relation_type,
            ForkRelation.license_snapshot, ForkRelation.id
        )
        .join(ForkRelation, ForkRelation.parent_id == Idea.id)
        .outerjoin(User, User.id == Idea.author_id)
        .where(ForkRelation.child_id == idea.id)
    )
    parents = []
    for parent_idea, parent_user, relation_type, license_snapshot, relation_id in parents_result.all():
        source_author = (
            (license_snapshot or {}).get("source_author_name")
            or (parent_user.username if parent_user else "匿名")
        )
        parent_visible = await can_view_idea(
            db, parent_idea, user.id if user else None
        )
        if not parent_visible:
            # Keep attribution/rights from the public-at-creation snapshot, but
            # never return a now-private Idea ID or its withdrawn content.
            if license_snapshot:
                parents.append(LineageNode(
                    id=f"withdrawn:{relation_id}",
                    color_hex=parent_idea.color_hex,
                    author=source_author,
                    title="已撤回的来源创意",
                    is_navigable=False,
                    relation_type=relation_type,
                    license_snapshot=license_snapshot,
                ))
            continue
        parents.append(LineageNode(
            id=str(parent_idea.id),
            color_hex=parent_idea.color_hex,
            author=source_author,
            title=parent_idea.content[:30],
            is_navigable=True,
            relation_type=relation_type,
            license_snapshot=license_snapshot,
        ))

    # 谱系图：子节点（最多10个）
    children_result = await db.execute(
        select(
            Idea, User, ForkRelation.relation_type, ForkRelation.license_snapshot
        )
        .join(ForkRelation, ForkRelation.child_id == Idea.id)
        .outerjoin(User, User.id == Idea.author_id)
        .where(ForkRelation.parent_id == idea.id)
        .order_by(ForkRelation.created_at.desc())
        .limit(10)
    )
    children = []
    for child_idea, child_user, relation_type, license_snapshot in children_result.all():
        if not await can_view_idea(db, child_idea, user.id if user else None):
            continue
        children.append(LineageNode(
            id=str(child_idea.id),
            color_hex=child_idea.color_hex,
            author=child_user.username if child_user else "匿名",
            title=child_idea.content[:30],
            is_navigable=True,
            relation_type=relation_type,
            license_snapshot=license_snapshot,
        ))

    access_role = None
    if user:
        if idea.author_id == user.id:
            access_role = "owner"
        else:
            grant_result = await db.execute(
                select(IdeaAccessGrant.role).where(
                    IdeaAccessGrant.idea_id == idea.id,
                    IdeaAccessGrant.user_id == user.id,
                    IdeaAccessGrant.status == "accepted",
                ).limit(1)
            )
            access_role = grant_result.scalar_one_or_none()

    return IdeaDetail(
        id=str(idea.id),
        content=idea.content,
        color_hex=idea.color_hex,
        source=idea.source,
        author=author,
        created_at=idea.created_at,
        fork_count=idea.fork_count,
        is_forkable=idea.is_forkable and await can_derive_from_idea(db, idea, user.id if user else None),
        publication_status=idea.publication_status,
        visibility=idea.visibility,
        license_code=idea.license_code,
        license_version=idea.license_version,
        access_role=access_role,
        is_in_vault=is_in_vault,
        lineage=Lineage(parents=parents, children=children),
    )


# ============================================================
# POST /ideas — 创建点子
# ============================================================

@router.post("", response_model=IdeaResponse, status_code=201)
@limiter.limit(CREATE_LIMIT)
async def create_idea(
    request: Request,
    req: IdeaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 先发后审：先入库
    color = random_color()
    idea = Idea(
        content=req.content,
        color_hex=color,
        source="ugc",
        author_id=user.id,
        border_style="gold-thin",
        ai_assisted=False,
    )
    db.add(idea)
    await db.flush()

    # 入作者仓库
    vault_item = VaultItem(
        user_id=user.id,
        idea_id=idea.id,
        is_producer=True,
    )
    db.add(vault_item)
    await db.commit()
    await db.refresh(idea)

    # 异步审核（不阻塞用户）— MVP 阶段同步审核，不通过则撤回
    # 审核统一使用全局 LLM 配置，避免用户通过自定义 endpoint 绕过审核
    passed, reason = await audit_content(db, req.content)
    await write_audit_log(db, idea.id, req.content, passed, reason)
    if not passed:
        idea.status = "rejected"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUDIT_FAILED", "message": reason or "内容审核不通过"}},
        )

    return IdeaResponse(
        id=str(idea.id),
        content=idea.content,
        color_hex=idea.color_hex,
        source=idea.source,
        author_id=str(idea.author_id),
        created_at=idea.created_at,
        border_style=idea.border_style,
        publication_status=idea.publication_status,
        visibility=idea.visibility,
        license_code=idea.license_code,
        allow_fork=idea.allow_fork,
    )


# ============================================================
# POST /ideas/fork — Fork 点子
# ============================================================

@router.post("/fork", response_model=ForkResponse, status_code=201)
async def fork_idea(
    req: IdeaForkRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 验证 parent
    parent_result = await db.execute(select(Idea).where(Idea.id == uuid.UUID(req.parent_id)).with_for_update())
    parent = parent_result.scalar_one_or_none()
    if parent is None or parent.status == "rejected" or not await can_view_idea(db, parent, user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "原点子不存在"}},
        )
    if not parent.is_forkable or not await can_derive_from_idea(db, parent, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORK_DISABLED", "message": "原点子不允许 fork"}},
        )
    if (
        await requires_custom_license_confirmation(db, [parent])
        and not req.confirm_custom_licenses
    ):
        raise HTTPException(
            status_code=422,
            detail={"error": {
                "code": "CUSTOM_LICENSE_CONFIRMATION_REQUIRED",
                "message": "衍生来源包含自定义授权，请阅读全部上游条款并明确确认",
            }},
        )

    # 审核
    passed, reason = await audit_content(db, req.content)
    if not passed:
        await write_audit_log(db, None, req.content, False, reason)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUDIT_FAILED", "message": reason or "内容审核不通过"}},
        )

    # 创建新点子
    color = random_color()
    new_idea = Idea(
        content=req.content,
        color_hex=color,
        source="fork",
        author_id=user.id,
        border_style="gold-thin",
        ai_assisted=False,
    )
    db.add(new_idea)
    await db.flush()

    # 建立 fork 关系
    relation = ForkRelation(
        child_id=new_idea.id,
        parent_id=parent.id,
        relation_type="fork",
        license_snapshot=await build_derivation_snapshot(
            db, parent,
            custom_license_acknowledged=req.confirm_custom_licenses,
            acknowledged_by=user.id,
        ),
    )
    db.add(relation)

    # 入 fork 者仓库
    vault_item = VaultItem(
        user_id=user.id,
        idea_id=new_idea.id,
        is_producer=True,
    )
    db.add(vault_item)

    # 更新原点子 fork_count —— 原子 SQL 自增，避免并发竞态
    # 不能用 ORM 读-改-写（parent.fork_count = parent.fork_count + 1），会丢失更新
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Idea)
        .where(Idea.id == parent.id)
        .values(
            fork_count=Idea.fork_count + 1,
            last_fork_at=now,
        )
    )

    # 通知原作者
    if parent.author_id and parent.author_id != user.id:
        await add_notification_if_enabled(
            db,
            user_id=parent.author_id,
            notification_type="forked",
            content=f"{user.username} fork 了你的『{parent.content[:20]}...』",
            idea_id=parent.id,
            actor_id=user.id,
        )

    await db.commit()
    await db.refresh(new_idea)

    return ForkResponse(
        id=str(new_idea.id),
        parent_id=str(parent.id),
        content=new_idea.content,
        color_hex=new_idea.color_hex,
        source=new_idea.source,
        border_style=new_idea.border_style,
    )



# ============================================================
# V2: explicit publication and direct private-Idea invitations
# ============================================================

@router.post("/{idea_id}/publish", response_model=IdeaResponse)
async def publish_idea(
    idea_id: uuid.UUID,
    req: IdeaPublishRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Idea).where(Idea.id == idea_id).with_for_update())
    idea = result.scalar_one_or_none()
    if idea is None or idea.author_id != user.id:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}})
    if not req.confirm_terms:
        raise HTTPException(status_code=400, detail={"error": {"code": "TERMS_NOT_CONFIRMED", "message": "必须确认授权条款"}})
    if idea.publication_status == "archived":
        raise HTTPException(status_code=409, detail={"error": {"code": "IDEA_ARCHIVED", "message": "归档点子不能直接发布"}})
    if req.license_code == "custom" and not (req.license_custom_text or "").strip():
        raise HTTPException(status_code=422, detail={"error": {"code": "LICENSE_TEXT_REQUIRED", "message": "自定义授权必须填写授权说明"}})
    if req.allow_fork and req.license_code not in ("attribution_adaptation", "custom"):
        raise HTTPException(status_code=422, detail={"error": {"code": "LICENSE_DERIVATIVE_MISMATCH", "message": "当前授权不允许开启 Fork"}})
    inherited_chain = await get_inherited_rights_chain(db, idea)
    if req.allow_fork and any(
        item.get("allow_fork") is not True
        or item.get("license_code") not in ("attribution_adaptation", "custom")
        for item in inherited_chain
    ):
        raise HTTPException(
            status_code=422,
            detail={"error": {
                "code": "INHERITED_LICENSE_BLOCKS_DERIVATION",
                "message": "上游来源授权不允许继续衍生，不能通过本次发布扩大权限",
            }},
        )

    passed, reason = await audit_content(db, idea.content)
    if not passed:
        raise HTTPException(status_code=403, detail={"error": {"code": "AUDIT_FAILED", "message": reason or "内容审核不通过"}})

    now = datetime.now(timezone.utc)
    idea.publication_status = "published"
    idea.visibility = req.visibility
    idea.license_code = req.license_code
    idea.license_text_snapshot = req.license_custom_text
    idea.license_version = req.license_version
    idea.allow_fork = req.allow_fork
    idea.is_forkable = req.allow_fork
    idea.published_at = now
    if idea.legacy_license_review_status == "pending":
        idea.legacy_license_review_status = "confirmed"
        idea.legacy_license_reviewed_at = now
    await db.commit()
    await cache.delete_pattern("explore:v3:*")
    await cache.delete(key_idea_detail(str(idea.id)))
    await db.refresh(idea)
    return IdeaResponse(
        id=str(idea.id), content=idea.content, color_hex=idea.color_hex,
        source=idea.source, author_id=str(idea.author_id),
        created_at=idea.created_at, border_style=idea.border_style,
        publication_status=idea.publication_status,
        visibility=idea.visibility,
        license_code=idea.license_code,
        allow_fork=idea.allow_fork,
    )


@router.post("/{idea_id}/unpublish")
async def unpublish_idea(
    idea_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Idea).where(Idea.id == idea_id).with_for_update())
    idea = result.scalar_one_or_none()
    if idea is None or idea.author_id != user.id:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}})
    idea.publication_status = "draft"
    idea.visibility = "private"
    idea.allow_fork = False
    idea.is_forkable = False
    await db.commit()
    await cache.delete_pattern("explore:v3:*")
    await cache.delete(key_idea_detail(str(idea.id)))
    return {"unpublished": True, "idea_id": str(idea.id)}


@router.get("/invites/inbox")
async def list_pending_idea_invites(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List pending private-Idea invitations addressed to the current user."""
    result = await db.execute(
        select(IdeaAccessGrant, Idea, User)
        .join(Idea, Idea.id == IdeaAccessGrant.idea_id)
        .join(User, User.id == IdeaAccessGrant.invited_by)
        .where(
            IdeaAccessGrant.user_id == user.id,
            IdeaAccessGrant.status == "pending",
            Idea.visibility == "private",
            Idea.status != "rejected",
        )
        .order_by(IdeaAccessGrant.invited_at.desc())
    )
    return {
        "items": [
            {
                "invite_id": str(grant.id),
                "idea_id": str(idea.id),
                "idea_content": idea.content,
                "idea_color_hex": idea.color_hex,
                "role": grant.role,
                "invited_at": grant.invited_at,
                "inviter": {"id": str(inviter.id), "username": inviter.username},
            }
            for grant, idea, inviter in result.all()
        ]
    }


@router.get("/{idea_id}/invites")
async def list_idea_invites(
    idea_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List invite states for the owner of a private Idea."""
    idea_result = await db.execute(select(Idea).where(Idea.id == idea_id))
    idea = idea_result.scalar_one_or_none()
    if idea is None or idea.author_id != user.id:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}})
    if idea.visibility != "private":
        raise HTTPException(status_code=409, detail={"error": {"code": "IDEA_NOT_PRIVATE", "message": "仅私有点子支持邀请管理"}})
    result = await db.execute(
        select(IdeaAccessGrant, User)
        .join(User, User.id == IdeaAccessGrant.user_id)
        .where(IdeaAccessGrant.idea_id == idea_id)
        .order_by(IdeaAccessGrant.invited_at.desc())
    )
    return {
        "items": [
            {
                "invite_id": str(grant.id),
                "user_id": str(invitee.id),
                "username": invitee.username,
                "role": grant.role,
                "status": grant.status,
                "invited_at": grant.invited_at,
                "responded_at": grant.responded_at,
                "revoked_at": grant.revoked_at,
            }
            for grant, invitee in result.all()
        ]
    }


@router.post("/{idea_id}/invites/{invite_id}/decline")
async def decline_private_idea_invite(
    idea_id: uuid.UUID,
    invite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(IdeaAccessGrant).where(
            IdeaAccessGrant.id == invite_id,
            IdeaAccessGrant.idea_id == idea_id,
            IdeaAccessGrant.user_id == user.id,
            IdeaAccessGrant.status == "pending",
        ).with_for_update()
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "INVITE_NOT_FOUND", "message": "待处理邀请不存在"}})
    grant.status = "declined"
    grant.responded_at = datetime.now(timezone.utc)
    await db.commit()
    return {"declined": True, "invite_id": str(invite_id)}


@router.post("/{idea_id}/invites", status_code=201)
async def invite_to_private_idea(
    idea_id: uuid.UUID,
    req: IdeaInviteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Idea).where(Idea.id == idea_id).with_for_update())
    idea = result.scalar_one_or_none()
    if idea is None or idea.author_id != user.id:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}})
    if idea.visibility != "private":
        raise HTTPException(status_code=409, detail={"error": {"code": "IDEA_NOT_PRIVATE", "message": "仅私有点子支持直接邀请"}})
    try:
        invitee_id = uuid.UUID(req.user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_USER_ID", "message": "用户 ID 无效"}})
    if invitee_id == user.id:
        raise HTTPException(status_code=400, detail={"error": {"code": "SELF_INVITE", "message": "不能邀请自己"}})
    invitee_result = await db.execute(select(User.id).where(User.id == invitee_id))
    if invitee_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "USER_NOT_FOUND", "message": "用户不存在"}})

    grant_result = await db.execute(
        select(IdeaAccessGrant).where(
            IdeaAccessGrant.idea_id == idea.id,
            IdeaAccessGrant.user_id == invitee_id,
        ).with_for_update()
    )
    grant = grant_result.scalar_one_or_none()
    if grant and grant.status in ("pending", "accepted"):
        raise HTTPException(status_code=409, detail={"error": {"code": "INVITE_EXISTS", "message": "邀请已存在"}})
    if grant:
        grant.role = req.role
        grant.status = "pending"
        grant.invited_by = user.id
        grant.invited_at = datetime.now(timezone.utc)
        grant.responded_at = None
        grant.revoked_at = None
    else:
        grant = IdeaAccessGrant(
            idea_id=idea.id, user_id=invitee_id, role=req.role,
            status="pending", invited_by=user.id,
        )
        db.add(grant)
    await db.commit()
    await cache.delete(key_idea_detail(str(idea.id)))
    return {"invite_id": str(grant.id), "status": grant.status, "role": grant.role}


@router.post("/{idea_id}/invites/{invite_id}/accept")
async def accept_private_idea_invite(
    idea_id: uuid.UUID,
    invite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(IdeaAccessGrant, Idea).join(
            Idea, Idea.id == IdeaAccessGrant.idea_id
        ).where(
            IdeaAccessGrant.id == invite_id,
            IdeaAccessGrant.idea_id == idea_id,
            IdeaAccessGrant.user_id == user.id,
            IdeaAccessGrant.status == "pending",
        ).with_for_update(of=IdeaAccessGrant)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "INVITE_NOT_FOUND", "message": "待处理邀请不存在"}})
    grant, idea = row
    if idea.visibility != "private" or idea.status == "rejected":
        raise HTTPException(status_code=409, detail={"error": {"code": "INVITE_NO_LONGER_VALID", "message": "该创意已不再处于可邀请状态"}})
    grant.status = "accepted"
    grant.responded_at = datetime.now(timezone.utc)
    await db.commit()
    await cache.delete(key_idea_detail(str(idea_id)))
    await cache.delete(key_user_vault(str(user.id)))
    return {"accepted": True, "idea_id": str(idea_id), "role": grant.role}


@router.delete("/{idea_id}/invites/{invite_id}")
async def revoke_private_idea_invite(
    idea_id: uuid.UUID,
    invite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    idea_result = await db.execute(select(Idea).where(Idea.id == idea_id))
    idea = idea_result.scalar_one_or_none()
    if idea is None or idea.author_id != user.id:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}})
    grant_result = await db.execute(
        select(IdeaAccessGrant).where(
            IdeaAccessGrant.id == invite_id,
            IdeaAccessGrant.idea_id == idea_id,
        ).with_for_update()
    )
    grant = grant_result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "INVITE_NOT_FOUND", "message": "邀请不存在"}})
    grant.status = "revoked"
    grant.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await cache.delete(key_idea_detail(str(idea_id)))
    await cache.delete(key_user_vault(str(grant.user_id)))
    return {"revoked": True, "invite_id": str(invite_id)}

# ============================================================
# Private Idea async contributions
# ============================================================

async def _get_private_collaboration_idea(db: AsyncSession, idea_id: uuid.UUID) -> Idea:
    result = await db.execute(select(Idea).where(Idea.id == idea_id))
    idea = result.scalar_one_or_none()
    if (
        idea is None
        or idea.visibility != "private"
        or idea.status == "rejected"
        or idea.publication_status == "archived"
    ):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "IDEA_NOT_FOUND", "message": "私有创意不存在或不可协作"}},
        )
    return idea


async def _require_accepted_contributor(
    db: AsyncSession,
    idea_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> IdeaAccessGrant:
    query = select(IdeaAccessGrant).where(
        IdeaAccessGrant.idea_id == idea_id,
        IdeaAccessGrant.user_id == user_id,
        IdeaAccessGrant.status == "accepted",
        IdeaAccessGrant.role == "contributor",
    )
    if for_update:
        # Serialize write operations against owner-side invite revocation.
        query = query.with_for_update()
    result = await db.execute(query)
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "CONTRIBUTOR_ACCESS_REQUIRED", "message": "需要接受协作者邀请后才能提交贡献"}},
        )
    return grant


@router.post("/{idea_id}/contributions", status_code=201)
async def submit_idea_contribution(
    idea_id: uuid.UUID,
    req: IdeaContributionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    idea = await _get_private_collaboration_idea(db, idea_id)
    if idea.author_id == user.id:
        raise HTTPException(status_code=400, detail={"error": {"code": "OWNER_CANNOT_CONTRIBUTE", "message": "创意作者请直接编辑自己的创意"}})
    await _require_accepted_contributor(db, idea_id, user.id, for_update=True)
    contribution = IdeaContribution(
        idea_id=idea_id,
        author_id=user.id,
        content=req.content.strip(),
        note=req.note.strip() if req.note else None,
        status="submitted",
    )
    if not contribution.content:
        raise HTTPException(status_code=422, detail={"error": {"code": "EMPTY_CONTRIBUTION", "message": "贡献内容不能为空"}})
    passed, reason = await audit_content(db, contribution.content)
    if not passed:
        await write_audit_log(db, idea.id, contribution.content, False, reason)
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "AUDIT_FAILED", "message": reason or "贡献内容审核不通过"}},
        )
    await write_audit_log(db, idea.id, contribution.content, True, None)
    db.add(contribution)
    await db.commit()
    await db.refresh(contribution)
    return {
        "id": str(contribution.id),
        "idea_id": str(idea_id),
        "author_id": str(user.id),
        "content": contribution.content,
        "note": contribution.note,
        "status": contribution.status,
        "created_at": contribution.created_at,
    }


@router.get("/{idea_id}/contributions")
async def list_idea_contributions(
    idea_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    idea = await _get_private_collaboration_idea(db, idea_id)
    if idea.author_id == user.id:
        condition = True
    else:
        await _require_accepted_contributor(db, idea_id, user.id)
        condition = IdeaContribution.author_id == user.id
    query = (
        select(IdeaContribution, User, IdeaVersion, IdeaVersionContribution)
        .join(User, User.id == IdeaContribution.author_id)
        .outerjoin(
            IdeaVersionContribution,
            IdeaVersionContribution.contribution_id == IdeaContribution.id,
        )
        .outerjoin(
            IdeaVersion,
            (IdeaVersion.id == IdeaVersionContribution.version_id)
            & (IdeaVersion.status == "published"),
        )
        .where(IdeaContribution.idea_id == idea_id)
    )
    if condition is not True:
        query = query.where(condition)
    query = query.order_by(IdeaContribution.created_at.desc())
    result = await db.execute(query)
    return {
        "items": [
            {
                "id": str(item.id),
                "author_id": str(item.author_id),
                "author_username": author.username,
                "content": item.content,
                "note": item.note,
                "status": item.status,
                "created_at": item.created_at,
                "reviewed_at": item.reviewed_at,
                "review_note": item.review_note if idea.author_id == user.id or item.author_id == user.id else None,
                "published_version": (
                    {
                        "id": str(version.id),
                        "version_number": version.version_number,
                        "published_at": version.published_at,
                        "change_summary": version.change_summary,
                    }
                    if version is not None else None
                ),
                "attribution_content_snapshot": (
                    attribution.content_snapshot if version is not None and attribution is not None else None
                ),
                "attribution_author_name": (
                    attribution.author_name_snapshot if version is not None and attribution is not None else None
                ),
            }
            for item, author, version, attribution in result.all()
        ]
    }


@router.patch("/{idea_id}/contributions/{contribution_id}")
async def update_idea_contribution(
    idea_id: uuid.UUID,
    contribution_id: uuid.UUID,
    req: IdeaContributionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    idea = await _get_private_collaboration_idea(db, idea_id)
    await _require_accepted_contributor(db, idea_id, user.id, for_update=True)
    result = await db.execute(
        select(IdeaContribution).where(
            IdeaContribution.id == contribution_id,
            IdeaContribution.idea_id == idea_id,
            IdeaContribution.author_id == user.id,
            IdeaContribution.status == "submitted",
        ).with_for_update()
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "CONTRIBUTION_NOT_EDITABLE", "message": "待审核贡献不存在或已锁定"}})
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail={"error": {"code": "EMPTY_CONTRIBUTION", "message": "贡献内容不能为空"}})
    passed, reason = await audit_content(db, content)
    if not passed:
        await write_audit_log(db, idea.id, content, False, reason)
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "AUDIT_FAILED", "message": reason or "贡献内容审核不通过"}},
        )
    await write_audit_log(db, idea.id, content, True, None)
    item.content = content
    item.note = req.note.strip() if req.note else None
    await db.commit()
    return {"updated": True, "id": str(item.id), "status": item.status}


@router.delete("/{idea_id}/contributions/{contribution_id}")
async def withdraw_idea_contribution(
    idea_id: uuid.UUID,
    contribution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_private_collaboration_idea(db, idea_id)
    await _require_accepted_contributor(db, idea_id, user.id, for_update=True)
    result = await db.execute(
        select(IdeaContribution).where(
            IdeaContribution.id == contribution_id,
            IdeaContribution.idea_id == idea_id,
            IdeaContribution.author_id == user.id,
            IdeaContribution.status == "submitted",
        ).with_for_update()
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "CONTRIBUTION_NOT_WITHDRAWABLE", "message": "待审核贡献不存在或已锁定"}})
    item.status = "withdrawn"
    await db.commit()
    return {"withdrawn": True, "id": str(item.id)}


@router.post("/{idea_id}/contributions/{contribution_id}/review")
async def review_idea_contribution(
    idea_id: uuid.UUID,
    contribution_id: uuid.UUID,
    req: IdeaContributionReview,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    idea = await _get_private_collaboration_idea(db, idea_id)
    if idea.author_id != user.id:
        raise HTTPException(status_code=404, detail={"error": {"code": "CONTRIBUTION_NOT_FOUND", "message": "贡献不存在"}})
    result = await db.execute(
        select(IdeaContribution).where(
            IdeaContribution.id == contribution_id,
            IdeaContribution.idea_id == idea_id,
            IdeaContribution.status == "submitted",
        ).with_for_update()
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "CONTRIBUTION_NOT_REVIEWABLE", "message": "待审核贡献不存在或已处理"}})
    item.status = req.decision
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_note = req.review_note.strip() if req.review_note else None
    await db.commit()
    return {
        "reviewed": True,
        "id": str(item.id),
        "status": item.status,
        "reviewed_at": item.reviewed_at,
    }

