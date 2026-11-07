from rest_framework.throttling import UserRateThrottle


class ReportThrottle(UserRateThrottle):
    scope = "report_create"
