"""Who is blocked from whom. Chat uses this to hide and refuse blocked conversations."""

from django.db.models import Q

from .models import Block


def blocked_user_ids(user) -> set[int]:
    """Ids of everyone ``user`` has blocked or who has blocked ``user``.

    A block works in both directions: neither person can see or use a conversation
    with the other. One query.
    """
    pairs = Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list(
        "blocker_id", "blocked_id"
    )
    return {other for pair in pairs for other in pair if other != user.pk}
