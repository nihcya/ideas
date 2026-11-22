"""Recursive Idea Universe graph and Inspired association privacy contracts."""
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from deps import get_current_user, get_optional_user, get_db
from main import app
from models import User, Idea, ForkRelation, IdeaAssociation, IdeaAccessGrant


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


def _public_idea(owner_id, content):
    from datetime import datetime, timezone
    return Idea(
        content=content,
        color_hex="#123456",
        source="ugc",
        author_id=owner_id,
        border_style="gold-thin",
        publication_status="published",
        visibility="public",
        license_code="attribution_adaptation",
        license_version="v1",
        allow_fork=True,
        is_forkable=True,
        published_at=datetime.now(timezone.utc),
        legacy_license_review_status="not_required",
    )


@pytest.mark.asyncio
async def test_recursive_graph_depth_and_inspired_edges_are_separate_from_lineage(db_session):
    owner = await _user(db_session, "universe_owner")
    parent = _public_idea(owner.id, "上游父创意")
    root = _public_idea(owner.id, "中心创意")
    child = _public_idea(owner.id, "下游衍生创意")
    grandchild = _public_idea(owner.id, "第二层衍生创意")
    db_session.add_all([parent, root, child, grandchild])
    await db_session.flush()
    db_session.add_all([
        ForkRelation(
            parent_id=parent.id, child_id=root.id, relation_type="fork",
            license_snapshot={"source_idea_id": str(parent.id), "source_author_name": owner.username},
        ),
        ForkRelation(
            parent_id=root.id, child_id=child.id, relation_type="merge",
            license_snapshot={"source_idea_id": str(root.id), "source_author_name": owner.username},
        ),
        ForkRelation(
            parent_id=child.id, child_id=grandchild.id, relation_type="evolve",
            license_snapshot={"source_idea_id": str(child.id), "source_author_name": owner.username},
        ),
        IdeaAssociation(
            source_idea_id=parent.id, target_idea_id=child.id,
            relation_type="inspired", created_by=owner.id, note="早期研究启发",
        ),
    ])
    await db_session.commit()

    active = {"user": owner}

    async def override_db():
        yield db_session

    async def override_user():
        return active["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_optional_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get(
                f"/api/ideas/{root.id}/graph",
                params={"depth": 2, "direction": "both", "include_inspired": True},
            )
            assert response.status_code == 200
            graph = response.json()
            node_ids = {node["id"] for node in graph["nodes"]}
            assert node_ids == {str(parent.id), str(root.id), str(child.id), str(grandchild.id)}
            assert any(edge["type"] == "fork" for edge in graph["edges"])
            assert any(edge["type"] == "merge" for edge in graph["edges"])
            assert any(edge["type"] == "evolve" for edge in graph["edges"])
            inspired = [edge for edge in graph["edges"] if edge["type"] == "inspired"]
            assert len(inspired) == 1
            assert inspired[0]["source"] == str(parent.id)
            assert inspired[0]["target"] == str(child.id)

            without_inspired = await client.get(
                f"/api/ideas/{root.id}/graph",
                params={"depth": 2, "direction": "both", "include_inspired": False},
            )
            assert without_inspired.status_code == 200
            assert all(edge["type"] != "inspired" for edge in without_inspired.json()["edges"])

            ancestors_only = await client.get(
                f"/api/ideas/{root.id}/graph",
                params={"depth": 3, "direction": "ancestors"},
            )
            assert ancestors_only.status_code == 200
            ancestor_ids = {node["id"] for node in ancestors_only.json()["nodes"]}
            assert ancestor_ids == {str(parent.id), str(root.id)}
            assert all(edge["target"] == str(root.id) for edge in ancestors_only.json()["edges"])

            descendants_only = await client.get(
                f"/api/ideas/{root.id}/graph",
                params={"depth": 3, "direction": "descendants", "include_inspired": False},
            )
            assert descendants_only.status_code == 200
            descendant_ids = {node["id"] for node in descendants_only.json()["nodes"]}
            assert descendant_ids == {str(root.id), str(child.id), str(grandchild.id)}
            assert all(edge["source"] in descendant_ids for edge in descendants_only.json()["edges"])

            too_deep = await client.get(
                f"/api/ideas/{root.id}/graph", params={"depth": 4}
            )
            assert too_deep.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)


@pytest.mark.asyncio
async def test_idea_search_only_returns_public_or_acl_visible_results(db_session):
    owner = await _user(db_session, "universe_search_owner")
    invited = await _user(db_session, "universe_search_invited")
    unrelated = await _user(db_session, "universe_search_unrelated")
    public = _public_idea(owner.id, "可搜索的公开创意")
    private_owner = Idea(
        content="可搜索的作者私有创意",
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        publication_status="draft",
        visibility="private",
    )
    private_invited = Idea(
        content="可搜索的受邀私有创意",
        color_hex="#654321",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        publication_status="draft",
        visibility="private",
    )
    private_unrelated = Idea(
        content="可搜索的无关私有创意",
        color_hex="#ABCDEF",
        source="ugc",
        author_id=unrelated.id,
        border_style="gold-thin",
        publication_status="draft",
        visibility="private",
    )
    db_session.add_all([public, private_owner, private_invited, private_unrelated])
    await db_session.flush()
    db_session.add(IdeaAccessGrant(
        idea_id=private_invited.id,
        user_id=invited.id,
        role="viewer",
        status="accepted",
        invited_by=owner.id,
    ))
    await db_session.commit()

    active = {"user": None}

    async def override_db():
        yield db_session

    async def override_user():
        return active["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_optional_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            anonymous = await client.get("/api/ideas/search", params={"q": "可搜索"})
            assert anonymous.status_code == 200
            assert {item["id"] for item in anonymous.json()["items"]} == {str(public.id)}

            active["user"] = owner
            owner_results = await client.get("/api/ideas/search", params={"q": "可搜索"})
            assert {item["id"] for item in owner_results.json()["items"]} == {
                str(public.id), str(private_owner.id), str(private_invited.id)
            }

            active["user"] = invited
            invited_results = await client.get("/api/ideas/search", params={"q": "可搜索"})
            assert {item["id"] for item in invited_results.json()["items"]} == {
                str(public.id), str(private_invited.id)
            }

            too_short = await client.get("/api/ideas/search", params={"q": " "})
            assert too_short.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)


@pytest.mark.asyncio
async def test_graph_enforces_max_node_cap_and_reports_truncation(db_session):
    owner = await _user(db_session, "universe_node_cap_owner")
    root = _public_idea(owner.id, "节点上限中心")
    children = [_public_idea(owner.id, f"节点上限子创意 {index}") for index in range(12)]
    db_session.add_all([root, *children])
    await db_session.flush()
    db_session.add_all([
        ForkRelation(
            parent_id=root.id,
            child_id=child.id,
            relation_type="fork",
            license_snapshot={"source_author_name": owner.username},
        )
        for child in children
    ])
    await db_session.commit()

    async def override_db():
        yield db_session

    async def override_user():
        return owner

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_optional_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get(
                f"/api/ideas/{root.id}/graph",
                params={"depth": 1, "direction": "descendants", "max_nodes": 10},
            )
        assert response.status_code == 200
        graph = response.json()
        assert len(graph["nodes"]) == 10
        assert graph["truncated"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)


@pytest.mark.asyncio
async def test_graph_enforces_max_edge_cap_and_reports_truncation(db_session):
    owner = await _user(db_session, "universe_edge_cap_owner")
    root = _public_idea(owner.id, "关系上限中心")
    children = [_public_idea(owner.id, f"关系上限创意 {index}") for index in range(25)]
    db_session.add_all([root, *children])
    await db_session.flush()
    relations = [
        ForkRelation(
            parent_id=root.id,
            child_id=child.id,
            relation_type="fork",
            license_snapshot={"source_author_name": owner.username},
        )
        for child in children
    ]
    for index, parent in enumerate(children):
        for child in children[index + 1:]:
            relations.append(ForkRelation(
                parent_id=parent.id,
                child_id=child.id,
                relation_type="evolve",
                license_snapshot={"source_author_name": owner.username},
            ))
    db_session.add_all(relations)
    await db_session.commit()

    async def override_db():
        yield db_session

    async def override_user():
        return owner

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_optional_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get(
                f"/api/ideas/{root.id}/graph",
                params={"depth": 2, "direction": "descendants", "max_nodes": 100},
            )
        assert response.status_code == 200
        graph = response.json()
        assert len(graph["nodes"]) == 26
        assert len(graph["edges"]) == 300
        assert graph["truncated"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)


@pytest.mark.asyncio
async def test_public_graph_uses_opaque_placeholder_for_restricted_ancestor(db_session):
    owner = await _user(db_session, "universe_public_owner")
    private_owner = await _user(db_session, "universe_private_owner")
    root = _public_idea(owner.id, "公开中心创意")
    private_parent = Idea(
        content="绝不能泄露的私有创意标题",
        color_hex="#ABCDEF",
        source="ugc",
        author_id=private_owner.id,
        border_style="gold-thin",
        publication_status="draft",
        visibility="private",
    )
    db_session.add_all([root, private_parent])
    await db_session.flush()
    relation = ForkRelation(
        parent_id=private_parent.id,
        child_id=root.id,
        relation_type="fork",
        license_snapshot={
            "source_idea_id": str(private_parent.id),
            "source_author_id": str(private_owner.id),
            "source_author_name": "冻结署名作者",
            "rights_chain": [{
                "idea_id": str(private_parent.id),
                "author_id": str(private_owner.id),
                "license_code": "attribution_adaptation",
                "allow_fork": True,
            }],
        },
    )
    db_session.add(relation)
    await db_session.commit()

    async def override_db():
        yield db_session

    async def anonymous():
        return None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_optional_user] = anonymous
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get(f"/api/ideas/{root.id}/graph", params={"depth": 1})
            assert response.status_code == 200
            raw = json.dumps(response.json(), ensure_ascii=False)
            graph = response.json()
            restricted = [node for node in graph["nodes"] if node["node_type"] == "restricted"]
            assert len(restricted) == 1
            assert restricted[0]["navigable"] is False
            assert restricted[0]["author"] == "冻结署名作者"
            assert str(private_parent.id) not in raw
            assert str(private_owner.id) not in raw
            assert "绝不能泄露的私有创意标题" not in raw
            assert any(edge["source"] == restricted[0]["id"] for edge in graph["edges"])
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)


@pytest.mark.asyncio
async def test_inspired_association_requires_target_owner_and_rejects_self(db_session):
    owner = await _user(db_session, "association_owner")
    other = await _user(db_session, "association_other")
    source = _public_idea(owner.id, "灵感来源")
    target = _public_idea(owner.id, "我的创意")
    foreign_target = _public_idea(other.id, "他人的创意")
    db_session.add_all([source, target, foreign_target])
    await db_session.commit()

    active = {"user": owner}

    async def override_db():
        yield db_session

    async def override_user():
        return active["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            created = await client.post(
                f"/api/ideas/{target.id}/associations",
                json={"source_idea_id": str(source.id), "note": "构思受到启发"},
            )
            assert created.status_code == 201
            association_id = created.json()["id"]

            duplicate = await client.post(
                f"/api/ideas/{target.id}/associations",
                json={"source_idea_id": str(source.id)},
            )
            assert duplicate.status_code == 409

            self_link = await client.post(
                f"/api/ideas/{target.id}/associations",
                json={"source_idea_id": str(target.id)},
            )
            assert self_link.status_code == 422

            forbidden = await client.post(
                f"/api/ideas/{foreign_target.id}/associations",
                json={"source_idea_id": str(source.id)},
            )
            assert forbidden.status_code == 404

            deleted = await client.delete(
                f"/api/ideas/{target.id}/associations/{association_id}"
            )
            assert deleted.status_code == 200
            assert await db_session.get(IdeaAssociation, uuid.UUID(association_id)) is None
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
