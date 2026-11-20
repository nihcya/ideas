"""演化路由：碰撞 + 演化"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Idea, VaultItem, ForkRelation
from schemas.idea import (
    CollideRequest, CollideResponse, CollideSuggestion,
    CollideConfirmRequest, CollideConfirmResponse,
    EvolveRequest, EvolveResponse, EvolveVariant,
    EvolveConfirmRequest, EvolveConfirmResponse,
)
from services.color_pool import random_color
from services.audit_service import audit_content
from services.crypto_service import decrypt
from services.deepseek_client import (
    call_collide_ai, call_evolve_ai, SAMPER_ANGLES,
)
from services.rate_limit import limiter, AI_LIMIT
from services.idea_access import can_view_idea, can_derive_from_idea

router = APIRouter(prefix="/ideas", tags=["evolve"])


# ============================================================
# POST /ideas/collide — 碰撞（AI 生成 3 方案）
# ============================================================

@router.post("/collide", response_model=CollideResponse)
@limiter.limit(AI_LIMIT)
async def collide(
    request: Request,
    req: CollideRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a_result = await db.execute(select(Idea).where(Idea.id == uuid.UUID(req.idea_a_id)))
    idea_a = a_result.scalar_one_or_none()
    b_result = await db.execute(select(Idea).where(Idea.id == uuid.UUID(req.idea_b_id)))
    idea_b = b_result.scalar_one_or_none()

    if (
        idea_a is None or idea_b is None
        or not await can_view_idea(db, idea_a, user.id)
        or not await can_view_idea(db, idea_b, user.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}},
        )

    if not await can_derive_from_idea(db, idea_a, user.id) or not await can_derive_from_idea(db, idea_b, user.id):
        raise HTTPException(status_code=403, detail={"error": {"code": "DERIVATIVE_NOT_ALLOWED", "message": "来源创意授权不允许碰撞衍生"}})

    # 调用 AI
    try:
        result = await call_collide_ai(idea_a.content, idea_b.content)
    except Exception as e:
        import logging
        logging.exception("AI collide call failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "AI_UNAVAILABLE", "message": "AI 服务暂时不可用，请稍后再试"}},
        )

    suggestions = [
        CollideSuggestion(**s) for s in result.get("suggestions", [])[:3]
    ]
    return CollideResponse(suggestions=suggestions)


# ============================================================
# POST /ideas/collide/confirm — 碰撞确认入仓库
# ============================================================

@router.post("/collide/confirm", response_model=CollideConfirmResponse, status_code=201)
async def collide_confirm(
    req: CollideConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 确认阶段重新加载并校验两个来源，不能信任此前 AI 预览时的权限状态。
    parents = []
    for pid in [req.idea_a_id, req.idea_b_id]:
        result = await db.execute(select(Idea).where(Idea.id == uuid.UUID(pid)))
        parent = result.scalar_one_or_none()
        if parent is None or not await can_view_idea(db, parent, user.id):
            raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "来源创意不存在"}})
        if not await can_derive_from_idea(db, parent, user.id):
            raise HTTPException(status_code=403, detail={"error": {"code": "DERIVATIVE_NOT_ALLOWED", "message": "来源创意授权不允许碰撞衍生"}})
        parents.append(parent)

    # 审核
    passed, reason = await audit_content(db, req.content)
    if not passed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUDIT_FAILED", "message": reason or "内容审核不通过"}},
        )

    color = random_color()
    new_idea = Idea(
        content=req.content,
        color_hex=color,
        source="merge",
        author_id=user.id,
        border_style="gold-thin",
        ai_assisted=req.ai_assisted,
    )
    db.add(new_idea)
    await db.flush()

    # 建立两个父关系
    for parent in parents:
        relation = ForkRelation(
            child_id=new_idea.id,
            parent_id=parent.id,
            relation_type="merge",
            license_snapshot={
                "license_code": parent.license_code,
                "license_text_snapshot": parent.license_text_snapshot,
                "license_version": parent.license_version,
                "source_author_id": str(parent.author_id) if parent.author_id else None,
                "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "allow_fork": parent.allow_fork,
            },
        )
        db.add(relation)

    # 入仓库
    vault_item = VaultItem(
        user_id=user.id,
        idea_id=new_idea.id,
        is_producer=True,
    )
    db.add(vault_item)
    await db.commit()
    await db.refresh(new_idea)

    return CollideConfirmResponse(
        id=str(new_idea.id),
        parent_ids=[req.idea_a_id, req.idea_b_id],
        source="merge",
        border_style=new_idea.border_style,
    )


# ============================================================
# POST /ideas/evolve — 演化（AI 生成 3 变体）
# ============================================================

@router.post("/evolve", response_model=EvolveResponse)
@limiter.limit(AI_LIMIT)
async def evolve(
    request: Request,
    req: EvolveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Idea).where(Idea.id == uuid.UUID(req.idea_id)))
    idea = result.scalar_one_or_none()
    if idea is None or not await can_view_idea(db, idea, user.id):
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}})
    if not await can_derive_from_idea(db, idea, user.id):
        raise HTTPException(status_code=403, detail={"error": {"code": "DERIVATIVE_NOT_ALLOWED", "message": "来源创意授权不允许演化"}})

    angle_desc = SAMPER_ANGLES.get(req.angle, "")
    try:
        # 用户自己的演化可用自己的 Key；从存储中解密后传入
        decrypted_key = decrypt(user.llm_api_key) if user.llm_api_key else None
        ai_result = await call_evolve_ai(
            idea.content, req.angle, angle_desc,
            user_api_url=user.llm_api_url, user_api_key=decrypted_key,
        )
    except Exception:
        import logging
        logging.exception("AI evolve call failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "AI_UNAVAILABLE", "message": "AI 服务暂时不可用，请稍后再试"}},
        )

    variants = [EvolveVariant(**v) for v in ai_result.get("variants", [])[:3]]
    return EvolveResponse(variants=variants)


# ============================================================
# POST /ideas/evolve/confirm — 演化确认入仓库
# ============================================================

@router.post("/evolve/confirm", response_model=EvolveConfirmResponse, status_code=201)
async def evolve_confirm(
    req: EvolveConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Idea).where(Idea.id == uuid.UUID(req.parent_id)))
    parent = result.scalar_one_or_none()
    if parent is None or not await can_view_idea(db, parent, user.id):
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "原点子不存在"}})
    if not await can_derive_from_idea(db, parent, user.id):
        raise HTTPException(status_code=403, detail={"error": {"code": "DERIVATIVE_NOT_ALLOWED", "message": "来源创意授权不允许演化"}})

    # 审核
    passed, reason = await audit_content(db, req.content)
    if not passed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUDIT_FAILED", "message": reason or "内容审核不通过"}},
        )

    color = random_color()
    new_idea = Idea(
        content=req.content,
        color_hex=color,
        source="evolve",
        author_id=user.id,
        border_style="gold-thin",
        ai_assisted=req.ai_assisted,
        evolved_from=req.angle,
    )
    db.add(new_idea)
    await db.flush()

    relation = ForkRelation(
        child_id=new_idea.id,
        parent_id=parent.id,
        relation_type="evolve",
        angle=req.angle,
        license_snapshot={
            "license_code": parent.license_code,
            "license_text_snapshot": parent.license_text_snapshot,
            "license_version": parent.license_version,
            "source_author_id": str(parent.author_id) if parent.author_id else None,
            "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "allow_fork": parent.allow_fork,
        },
    )
    db.add(relation)

    vault_item = VaultItem(
        user_id=user.id,
        idea_id=new_idea.id,
        is_producer=True,
    )
    db.add(vault_item)
    await db.commit()
    await db.refresh(new_idea)

    return EvolveConfirmResponse(
        id=str(new_idea.id),
        parent_id=str(parent.id),
        evolved_from=req.angle,
        source="evolve",
        border_style=new_idea.border_style,
    )
