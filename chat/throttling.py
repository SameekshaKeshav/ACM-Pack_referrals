from accounts.throttling import WindowedAnonThrottle


class MessageSendThrottle(WindowedAnonThrottle):
    """Limits how fast one signed-in user can send messages (default 30 a minute).

    Reuses the windowed rate parser from ``accounts.throttling`` but keys on the
    user rather than the IP address, so people on shared campus networks do not
    throttle each other. Polling and reading are not limited. Change the rate with
    the ``THROTTLE_MESSAGE_SEND`` environment variable.
    """

    scope = "message_send"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None  # unauthenticated callers are refused with 401 before this matters
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}
