"""设置路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User
from schemas.settings import SettingsResponse, SettingsUpdateRequest, _mask_api_key

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    user: User = Depends(get_current_user),
):
    return SettingsResponse(
        dark_mode=user.dark_mode,
        forkable=user.forkable,
        username=user.username,
        bio=user.bio or "",
        llm_api_url=user.llm_api_url or "",
        llm_api_key=_mask_api_key(user.llm_api_key or ""),
        llm_api_key_configured=bool(user.llm_api_key),
    )


@router.put("")
async def update_settings(
    req: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.dark_mode is not None:
        user.dark_mode = req.dark_mode
    if req.forkable is not None:
        user.forkable = req.forkable
    if req.bio is not None:
        user.bio = req.bio[:50]
    # 大模型配置：明文写入，空字符串表示清除
    if req.llm_api_url is not None:
        user.llm_api_url = req.llm_api_url.strip()
    if req.llm_api_key is not None:
        user.llm_api_key = req.llm_api_key.strip()
    await db.commit()
    return {"updated": True}
