"""Filtering for the people directory.

Kept out of the view so the query logic can be tested without HTTP, and so the
set of supported filters is readable in one place.
"""

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from .models import Profile


def _positive_int(params, name):
    """Read an optional integer query parameter, or 400 if it is not one."""
    raw = params.get(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError({name: "Must be a whole number."})
    if value < 0:
        raise ValidationError({name: "Must not be negative."})
    return value


MAX_MAJORS = 10


def _majors(params):
    """Every non-blank ``major`` value. Repeating the parameter adds alternatives."""
    values = params.getlist("major") if hasattr(params, "getlist") else [params.get("major", "")]
    majors = [value.strip() for value in values if value.strip()]
    if len(majors) > MAX_MAJORS:
        raise ValidationError({"major": f"At most {MAX_MAJORS} majors at once."})
    return majors


def visible_profiles():
    """Only verified members appear. Unverified accounts have not proved they
    are NC State students, and suspended ones are hidden by spec 4.6.
    """
    return (
        Profile.objects.filter(account_status=Profile.AccountStatus.ACTIVE)
        .select_related("user", "current_company")
        .order_by("user_id")
    )


def filter_directory(params):
    """Apply major / grad_year / company_id, all optional and combinable."""
    queryset = visible_profiles()

    majors = _majors(params)
    if majors:
        # Substring rather than exact: nobody types "Computer Science" the
        # same way twice. Repeating the parameter (?major=A&major=B) means
        # "A or B", which is what a row of checkboxes needs.
        match_any_major = Q()
        for major in majors:
            match_any_major |= Q(major__icontains=major)
        queryset = queryset.filter(match_any_major)

    grad_year = _positive_int(params, "grad_year")
    if grad_year is not None:
        queryset = queryset.filter(grad_year=grad_year)

    company_id = _positive_int(params, "company_id")
    if company_id is not None:
        # "Who is at this company" means current employer or any past role
        # there - that is the question the product exists to answer.
        queryset = queryset.filter(
            Q(current_company_id=company_id)
            | Q(user__past_roles__company_id=company_id)
        ).distinct()

    return queryset
