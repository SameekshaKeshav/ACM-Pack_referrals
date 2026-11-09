from django.contrib import admin

from chat.models import Message
from companies.models import InterviewExperience
from accounts.models import Profile

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "target_type", "target_id", "reason", "status", "created_at")
    list_filter = ("target_type", "reason", "status")
    actions = ("mark_reviewed", "suspend_user")

    @admin.action(description="Mark selected reports reviewed")
    def mark_reviewed(self, request, queryset):
        queryset.update(status=Report.Status.REVIEWED)

    @admin.action(description="Suspend users named by selected reports")
    def suspend_user(self, request, queryset):
        user_ids = set()
        for report in queryset:
            if report.target_type == Report.TargetType.USER:
                user_ids.add(report.target_id)
            elif report.target_type == Report.TargetType.MESSAGE:
                user_ids.update(
                    Message.objects.filter(pk=report.target_id).values_list("sender_id", flat=True)
                )
            elif report.target_type == Report.TargetType.EXPERIENCE:
                user_ids.update(
                    InterviewExperience.objects.filter(pk=report.target_id).values_list(
                        "author_id", flat=True
                    )
                )
        Profile.objects.filter(user_id__in=user_ids).update(
            account_status=Profile.AccountStatus.SUSPENDED
        )
