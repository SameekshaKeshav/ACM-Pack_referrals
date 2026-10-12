from django.contrib import admin

from .models import Conversation, ConversationParticipant, Message


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")
    inlines = [ConversationParticipantInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "sender", "created_at", "read_status")
