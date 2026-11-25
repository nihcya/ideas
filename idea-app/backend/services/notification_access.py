"""SQL visibility predicate for notifications linked to Ideas or collaboration workspaces."""
from sqlalchemy import select, or_, and_

from models import Idea, IdeaAccessGrant, Notification, CollaborationMember


def visible_notification_predicate(user_id):
    """Hide resource notifications after the recipient loses the linked resource ACL."""
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

    visible_linked_collaboration = select(CollaborationMember.id).where(
        CollaborationMember.collaboration_id == Notification.collaboration_id,
        CollaborationMember.user_id == user_id,
        CollaborationMember.status.in_(["accepted", "pending"]),
    ).exists()

    # Historical/resource-free notifications remain visible. For private
    # collaboration notifications (no public Idea link), current membership
    # or a pending invite is required. Public Idea notifications continue to
    # use the Idea ACL even if workspace membership later ends.
    return or_(
        and_(
            Notification.idea_id.is_(None),
            Notification.collaboration_id.is_(None),
        ),
        and_(
            Notification.idea_id.is_not(None),
            visible_linked_idea,
        ),
        and_(
            Notification.idea_id.is_(None),
            Notification.collaboration_id.is_not(None),
            visible_linked_collaboration,
        ),
    )
