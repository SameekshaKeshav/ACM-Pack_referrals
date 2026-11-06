from django.contrib import admin
from django.utils import timezone

from .models import AlumniAccessRequest, PastRole, Profile


def _suspend_revoked_alumni(emails):
    """Suspend accounts whose only route in was a request that is now rejected.

    Rejecting a request does not by itself take access away: nothing in the
    login or verify path reads AlumniAccessRequest, so the account stays
    reachable. Suspending the profile is what removes them from the directory
    and the company pages, stops them sending or receiving referral asks, and
    stops anyone sending them a connection request.

    It does not close everything. POST /api/connections/ checks the
    recipient's status but not the sender's, so a suspended user can still
    send connection requests, and their own profile and the chat and company
    reads stay open. Those are recorded in the security checklist.

    Two addresses are deliberately left alone: one still covered by another
    approved request, and an @ncsu.edu account, whose eligibility never came
    from a request at all. Both are recognised by verified_via, which is set
    once at signup from the address itself.

    Returns the number of profiles changed.
    """
    count = 0
    for email in emails:
        if AlumniAccessRequest.is_approved_email(email):
            continue  # another approved request still covers this address
        count += (
            Profile.objects.filter(
                user__email__iexact=email,
                verified_via=Profile.VerifiedVia.ADMIN_APPROVAL,
            )
            .exclude(account_status=Profile.AccountStatus.SUSPENDED)
            .update(account_status=Profile.AccountStatus.SUSPENDED)
        )
    return count


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

    @admin.action(description="Reject: refuse these, and suspend any account they let in")
    def reject_requests(self, request, queryset):
        # Collected before _review flips the status, so is_approved_email()
        # below sees the post-rejection picture.
        emails = set(
            queryset.exclude(status=AlumniAccessRequest.Status.REJECTED).values_list(
                "email", flat=True
            )
        )
        self._review(request, queryset, AlumniAccessRequest.Status.REJECTED)
        suspended = _suspend_revoked_alumni(emails)
        if suspended:
            self.message_user(
                request,
                f"{suspended} profile(s) suspended, so they are hidden from "
                "the directory and can no longer exchange referral asks. This "
                "does not sign them out: a token they already hold keeps "
                "working, and they can still send connection requests. See the "
                "security checklist.",
            )
