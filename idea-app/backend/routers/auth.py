"""认证路由：注册 + 登录 + 登出"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from deps import get_db
from models import User
from schemas.auth import RegisterRequest, LoginRequest, AuthResponse
from services.jwt_service import create_access_token, revoke_token
from services.rate_limit import limiter, LOGIN_LIMIT, REGISTER_LIMIT

router = APIRouter(prefix="/auth", tags=["auth"])

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def _hash_password(password: str) -> str:
    return _pwd.hash(password)


def _verify_password(password: str, hash_: str) -> bool:
    try:
        return _pwd.verify(password, hash_)
    except Exception:
        return False


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit(REGISTER_LIMIT)
async def register(request: Request, req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "ALREADY_EXISTS", "message": "用户名已存在"}},
        )

    user = User(
        username=req.username,
        password_hash=_hash_password(req.password),
        bio=req.bio,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.username)
    return AuthResponse(user_id=str(user.id), username=user.username, token=token)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(LOGIN_LIMIT)
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if user is None or not _verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "用户名或密码错误"}},
        )

    token = create_access_token(user.id, user.username)
    return AuthResponse(user_id=str(user.id), username=user.username, token=token)


@router.post("/logout")
async def logout(
    authorization: str | None = Header(None),
):
    """登出：将当前 token 加入黑名单（H2 JWT 撤销机制）。

    前端登出时调用此接口，后端把 token 的 jti 写入 Redis 黑名单，
    TTL 为 token 剩余有效期。之后该 token 即便被持有也无法再用。
    """
    if not authorization or not authorization.startswith("Bearer "):
        # 无 token 视为已登出，幂等返回
        return {"logged_out": True}
    token = authorization.split(" ", 1)[1]
    await revoke_token(token)
    return {"logged_out": True}
