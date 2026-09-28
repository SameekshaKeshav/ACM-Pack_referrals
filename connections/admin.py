from django.contrib import admin

from .models import ConnectionRequest, Report


@admin.register(ConnectionRequest)
class ConnectionRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "status", "created_at")
    list_filter = ("status",)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "reported_user", "status", "created_at")
    list_filter = ("status",)
