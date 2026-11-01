from django.contrib import admin
from django.utils import timezone

from .models import AlumniAccessRequest, PastRole, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "major",
        "grad_year",
        "open_to_connect",
        "account_status",
        "verified_via",
    )
    list_filter = ("account_status", "verified_via")


@admin.register(PastRole)
class PastRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role_title", "start_date", "end_date")


@admin.register(AlumniAccessRequest)
class AlumniAccessRequestAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "full_name",
        "unity_id",
        "grad_year",
        "major",
        "status",
        "unity_id_clash",
        "created_at",
        "reviewed_by",
    )
    list_filter = ("status",)
    search_fields = ("email", "full_name", "unity_id", "major")
    readonly_fields = ("created_at", "reviewed_by", "reviewed_at")
    actions = ("approve_requests", "reject_requests")

    @admin.display(boolean=True, description="Unity ID clash")
    def unity_id_clash(self, obj):
        """Another request claims this Unity ID - a typo, or a guess at a real one."""
        return obj.other_requests_with_this_unity_id().exists()

    def _review(self, request, queryset, new_status):
        """Set a status once, recording who did it.

        Filtered to requests not already in that status so re-running the
        action does not overwrite the original reviewer and timestamp.
        """
        changed = queryset.exclude(status=new_status).update(
            status=new_status, reviewed_by=request.user, reviewed_at=timezone.now()
        )
        skipped = queryset.count() - changed
        message = f"{changed} request(s) marked {new_status}."
        if skipped:
            message += f" {skipped} already were, and were left alone."
        self.message_user(request, message)

    @admin.action(description="Approve: let these addresses sign in")
    def approve_requests(self, request, queryset):
        self._review(request, queryset, AlumniAccessRequest.Status.APPROVED)

    @admin.action(description="Reject these requests")
    def reject_requests(self, request, queryset):
        self._review(request, queryset, AlumniAccessRequest.Status.REJECTED)
