"""Who is affiliated with a company, and how."""

from accounts.models import PastRole, Profile


def _display_name(user):
    return user.get_full_name() or user.get_username()


def affiliated_users(company):
    """Everyone linked to ``company``, newest affiliation first.

    The spec treats a company page as "who from NC State has worked here", so
    this covers both halves of that: explicit PastRole entries, and people
    whose profile names this as their current employer. A person with both
    appears once, as current.
    """
    rows = []
    seen = set()

    current = (
        Profile.objects.filter(current_company=company)
        .select_related("user")
        .order_by("user__id")
    )
    for profile in current:
        seen.add(profile.user_id)
        rows.append(
            {
                "user_id": profile.user_id,
                "name": _display_name(profile.user),
                "major": profile.major,
                "grad_year": profile.grad_year,
                "role_title": profile.current_role,
                "start_date": None,
                "end_date": None,
                "is_current": True,
            }
        )

    past = (
        PastRole.objects.filter(company=company)
        .select_related("user", "user__profile")
        .order_by("-start_date", "user__id")
    )
    for role in past:
        if role.user_id in seen:
            continue
        profile = getattr(role.user, "profile", None)
        rows.append(
            {
                "user_id": role.user_id,
                "name": _display_name(role.user),
                "major": profile.major if profile else "",
                "grad_year": profile.grad_year if profile else None,
                "role_title": role.role_title,
                "start_date": role.start_date,
                "end_date": role.end_date,
                "is_current": False,
            }
        )

    return rows
