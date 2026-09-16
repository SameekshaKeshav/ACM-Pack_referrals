from django.contrib import admin

from .models import (
    Company,
    ConnectionRequest,
    Conversation,
    Message,
    PastRole,
    Profile,
    Report,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "major", "grad_year", "open_to_connect", "account_status")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry_tag")
    search_fields = ("name",)


@admin.register(PastRole)
class PastRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role_title", "start_date", "end_date")


@admin.register(ConnectionRequest)
class ConnectionRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "status", "created_at")
    list_filter = ("status",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "sender", "created_at", "read_status")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "reported_user", "status", "created_at")
    list_filter = ("status",)
