"""路由汇总"""
from fastapi import APIRouter

from .auth import router as auth_router
from .ideas import router as ideas_router
from .evolve import router as evolve_router
from .vault import router as vault_router
from .spark import router as spark_router
from .users import router as users_router
from .notifications import router as notifications_router
from .settings import router as settings_router
from .idea_versions import router as idea_versions_router
from .collaborations import router as collaborations_router


def get_all_routers() -> list[APIRouter]:
    return [
        auth_router,
        ideas_router,
        evolve_router,
        vault_router,
        spark_router,
        users_router,
        notifications_router,
        settings_router,
        idea_versions_router,
        collaborations_router,
    ]
