"""SQL visibility predicate for notifications linked to Ideas."""
from sqlalchemy import select, or_, and_

from models import Idea, IdeaAccessGrant, Notification


def visible_notification_predicate(user_id):
    """Hide notifications whose linked Idea is no longer visible to the recipient."""
    visible_linked_idea = select(Idea.id).where(
        Idea.id == Notification.idea_id,
        or_(
            Idea.author_id == user_id,
            and_(
                Idea.publication_status == "published",
                Idea.visibility == "public",
                Idea.status == "active",
            ),
            select(IdeaAccessGrant.id).where(
                IdeaAccessGrant.idea_id == Idea.id,
                IdeaAccessGrant.user_id == user_id,
                IdeaAccessGrant.status == "accepted",
            ).exists(),
        ),
    ).exists()
    # Non-Idea notifications remain visible. Historical notifications with a
    # null idea_id cannot be retroactively associated with a resource.
    return or_(Notification.idea_id.is_(None), visible_linked_idea)
