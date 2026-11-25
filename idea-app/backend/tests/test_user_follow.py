import pytest
from sqlalchemy import select
from httpx import ASGITransport, AsyncClient

from deps import get_current_user, get_db, get_optional_user
from main import app
from models import User, UserFollow


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio=f"{username} bio")
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_creator_follow_unfollow_profile_counts_and_public_lists(db_session):
    follower = await _user(db_session, "follow_alice")
    creator = await _user(db_session, "follow_bob")
    await db_session.commit()

    active = {"user": follower}

    async def override_db():
        yield db_session

    async def override_user():
        return active["user"]

    async def override_optional_user():
        return active["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_optional_user] = override_optional_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            followed = await client.post(f"/api/users/{creator.id}/follow")
            assert followed.status_code == 200
            assert followed.json()["following"] is True

            idempotent = await client.post(f"/api/users/{creator.id}/follow")
            assert idempotent.status_code == 200

            self_follow = await client.post(f"/api/users/{follower.id}/follow")
            assert self_follow.status_code == 422

            profile = await client.get(f"/api/users/{creator.id}")
            assert profile.status_code == 200
            assert profile.json()["is_following"] is True
            assert profile.json()["is_self"] is False
            assert profile.json()["stats"]["followers"] == 1

            followers = await client.get(f"/api/users/{creator.id}/followers")
            assert followers.status_code == 200
            assert followers.json()["items"][0]["id"] == str(follower.id)

            following = await client.get(f"/api/users/{follower.id}/following")
            assert following.status_code == 200
            assert following.json()["items"][0]["id"] == str(creator.id)

            active["user"] = creator
            own_profile = await client.get(f"/api/users/{creator.id}")
            assert own_profile.json()["is_self"] is True
            assert own_profile.json()["is_following"] is False

            active["user"] = follower
            unfollowed = await client.delete(f"/api/users/{creator.id}/follow")
            assert unfollowed.status_code == 200
            assert unfollowed.json()["following"] is False

            profile_after = await client.get(f"/api/users/{creator.id}")
            assert profile_after.json()["stats"]["followers"] == 0
            assert profile_after.json()["is_following"] is False

        assert await db_session.scalar(
            select(UserFollow.id).where(
                UserFollow.follower_id == follower.id,
                UserFollow.following_id == creator.id,
            )
        ) is None
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)
