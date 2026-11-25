"""Explicit environment allowlist for privileged moderation operations."""
from __future__ import annotations

import uuid

from config import settings


def is_admin_user(user) -> bool:
    if user is None:
        return False
    allowed = set()
    for raw in settings.admin_user_ids.split(","):
        value = raw.strip()
        if not value:
            continue
        try:
            allowed.add(uuid.UUID(value))
        except ValueError:
            # Invalid deployment configuration never grants privileges.
            continue
    return user.id in allowed
