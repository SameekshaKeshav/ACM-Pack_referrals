from rest_framework.pagination import LimitOffsetPagination


class DirectoryPagination(LimitOffsetPagination):
    """limit/offset, as the tracker specifies.

    The cap matters: without one, ?limit=100000 would serialise every profile
    on the site in a single unauthenticated-cost query.
    """

    default_limit = 20
    max_limit = 100
