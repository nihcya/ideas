import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func

from deps import get_db, get_current_user
from main import app
from models import User, Notification
from services.notification_preferences import add_notification_if_enabled


@pytest.mark.asyncio
async def test_notification_preferences_default_enabled_and_suppress_future_events(db_session):
    user = User(username="notification_pref_user", password_hash="test-hash", bio="")
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    async def override_db():
        yield db_session

    async def override_user():
        return await db_session.get(User, user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            defaults = await client.get("/api/notifications/preferences")
            assert defaults.status_code == 200
            default_map = {item["notification_type"]: item["enabled"] for item in defaults.json()["items"]}
            assert default_map["forked"] is True
            assert default_map["collab_published"] is True

            updated = await client.put(
                "/api/notifications/preferences",
                json={"items": [
                    {"notification_type": "forked", "enabled": False},
                    {"notification_type": "collab_published", "enabled": True},
                ]},
            )
            assert updated.status_code == 200
            updated_map = {item["notification_type"]: item["enabled"] for item in updated.json()["items"]}
            assert updated_map["forked"] is False
            assert updated_map["collab_published"] is True

            unknown = await client.put(
                "/api/notifications/preferences",
                json={"items": [{"notification_type": "secret_type", "enabled": False}]},
            )
            assert unknown.status_code == 422

        assert await add_notification_if_enabled(
            db_session,
            user_id=user_id,
            notification_type="forked",
            content="this should be suppressed",
        ) is None
        assert await add_notification_if_enabled(
            db_session,
            user_id=user_id,
            notification_type="collab_published",
            content="this should be delivered",
        ) is not None
        await db_session.commit()
        count = await db_session.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )
        assert count == 1
        notification = await db_session.scalar(
            select(Notification).where(Notification.user_id == user_id)
        )
        assert notification.type == "collab_published"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
