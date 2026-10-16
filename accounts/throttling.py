import re

from rest_framework.throttling import SimpleRateThrottle


class WindowedAnonThrottle(SimpleRateThrottle):
    """Anonymous throttle that understands windows like ``5/15min``.

    DRF's own parser only reads the first character of the period, so a rate
    of ``5/15min`` raises rather than meaning what it says. This accepts an
    optional multiplier before the unit.
    """

    RATE_RE = re.compile(r"^(?P<count>\d+)/(?P<multiplier>\d*)(?P<unit>[smhd])")
    UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)
        match = self.RATE_RE.match(rate)
        if match is None:
            raise ValueError(f"Unparseable throttle rate: {rate!r}")
        multiplier = int(match["multiplier"] or 1)
        return (
            int(match["count"]),
            multiplier * self.UNIT_SECONDS[match["unit"]],
        )

    def get_cache_key(self, request, view):
        # Always throttle by IP. These endpoints are unauthenticated by
        # definition, so there is no user to key on.
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class CodeRequestThrottle(WindowedAnonThrottle):
    """Limits how often an address can be made to receive a code."""

    scope = "code_request"


class VerifyAttemptThrottle(WindowedAnonThrottle):
    """Limits how fast one source can submit codes.

    This protects the server from flooding. It does not, on its own, stop
    brute force - an attacker with many addresses gets many windows. The
    per-code attempt cap in VerificationCode is what bounds guessing.
    """

    scope = "verify_attempt"
