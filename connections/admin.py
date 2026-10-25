from django.contrib import admin

from .models import Block, ConnectionRequest


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")


@admin.register(ConnectionRequest)
class ConnectionRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "status", "created_at")
    list_filter = ("status",)
