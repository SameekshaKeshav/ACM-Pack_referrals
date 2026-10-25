from rest_framework.pagination import LimitOffsetPagination


class ReferralPagination(LimitOffsetPagination):
    """limit/offset, the same shape as the people directory.

    The cap stops ``?limit=100000`` from serialising every row in one request.
    """

    default_limit = 20
    max_limit = 100
