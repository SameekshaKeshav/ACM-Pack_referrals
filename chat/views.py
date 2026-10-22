from django.db.models import Count, F, Max, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from connections.blocks import blocked_user_ids

from .models import Conversation, ConversationParticipant, Message
from .serializers import (
    ConversationListSerializer,
    MarkReadResultSerializer,
    MessageSerializer,
    SendMessageSerializer,
)
from .throttling import MessageSendThrottle

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


class AppHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"app": "chat", "status": "ok"})


def get_conversation_for_participant(conversation_id, user):
    """Return the conversation, or raise 404 (unknown) / 403 (not a participant or blocked).

    Every chat endpoint goes through here so a user can only ever touch
    conversations they are part of, and never one with someone they have blocked or
    who has blocked them. Blocking is soft: the messages stay stored.
    """
    try:
        conversation = Conversation.objects.get(pk=conversation_id)
    except Conversation.DoesNotExist:
        raise NotFound("Conversation not found.")
    if not conversation.conversation_participants.filter(user=user).exists():
        raise PermissionDenied("You are not a participant in this conversation.")
    other_ids = conversation.conversation_participants.exclude(user=user).values_list(
        "user_id", flat=True
    )
    if blocked_user_ids(user).intersection(other_ids):
        raise PermissionDenied("This conversation is not available.")
    return conversation


def _last_message_field(field):
    return Subquery(
        Message.objects.filter(conversation=OuterRef("pk"))
        .order_by("-created_at", "-id")
        .values(field)[:1]
    )


class ConversationListView(generics.ListAPIView):
    """``GET /api/chat/conversations/``: the caller's conversations, newest activity first."""

    serializer_class = ConversationListSerializer

    def get_queryset(self):
        user = self.request.user
        participants = ConversationParticipant.objects.select_related(
            "user__profile__current_company"
        )
        return (
            Conversation.objects.filter(conversation_participants__user=user)
            # Soft block: hide conversations with anyone blocked in either direction.
            .exclude(conversation_participants__user_id__in=blocked_user_ids(user))
            .prefetch_related(Prefetch("conversation_participants", queryset=participants))
            .annotate(
                last_message_id=_last_message_field("id"),
                last_message_sender_id=_last_message_field("sender_id"),
                last_message_body=_last_message_field("body_text"),
                last_message_created_at=_last_message_field("created_at"),
                updated_at=Coalesce(Max("messages__created_at"), F("created_at")),
                unread_count=Count(
                    "messages",
                    filter=Q(messages__read_status=False) & ~Q(messages__sender=user),
                ),
            )
            .order_by("-updated_at", "-id")
        )


def _parse_int(params, name, default=None, minimum=1, maximum=None):
    raw = params.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError({name: "Must be an integer."})
    if value < minimum or (maximum is not None and value > maximum):
        bound = f"between {minimum} and {maximum}" if maximum else f"at least {minimum}"
        raise ValidationError({name: f"Must be {bound}."})
    return value


class ConversationMessagesView(generics.GenericAPIView):
    """``GET /api/chat/conversations/<id>/messages/``: history, older history, or a poll."""

    serializer_class = MessageSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("limit", int, description="1-100, default 50."),
            OpenApiParameter(
                "after", int, description="Poll: only messages with an id greater than this."
            ),
            OpenApiParameter(
                "before",
                OpenApiTypes.DATETIME,
                description="Older history: created_at cursor; requires before_id.",
            ),
            OpenApiParameter(
                "before_id", int, description="Older history: id cursor; requires before."
            ),
        ],
        responses=MessageSerializer(many=True),
    )
    def get(self, request, conversation_id):
        conversation = get_conversation_for_participant(conversation_id, request.user)
        params = request.query_params

        limit = _parse_int(params, "limit", DEFAULT_PAGE_SIZE, maximum=MAX_PAGE_SIZE)
        after = _parse_int(params, "after", minimum=0)
        before_id = _parse_int(params, "before_id")
        before_raw = params.get("before")

        if (before_raw is not None or before_id is not None) and after is not None:
            raise ValidationError("Use either before/before_id or after, not both.")
        if (before_raw is None) != (before_id is None):
            raise ValidationError("before and before_id must be sent together.")

        messages = Message.objects.filter(conversation=conversation)

        if after is not None:
            # Poll: everything newer than the last message the client has, oldest first.
            page = list(messages.filter(id__gt=after).order_by("id")[:limit])
        else:
            if before_raw is not None:
                before = parse_datetime(before_raw)
                if before is None or before.tzinfo is None:
                    raise ValidationError(
                        {"before": "Must be an ISO 8601 timestamp with a timezone."}
                    )
                # Exclusive (created_at, id) cursor so equal timestamps are not skipped.
                messages = messages.filter(
                    Q(created_at__lt=before) | Q(created_at=before, id__lt=before_id)
                )
            # The most recent `limit` messages, returned oldest first.
            page = list(messages.order_by("-created_at", "-id")[:limit])[::-1]

        return Response(MessageSerializer(page, many=True).data)


class SendMessageView(generics.GenericAPIView):
    """``POST /api/chat/messages/``: send a message as the authenticated user."""

    serializer_class = SendMessageSerializer
    throttle_classes = [MessageSendThrottle]

    @extend_schema(request=SendMessageSerializer, responses={201: MessageSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = get_conversation_for_participant(
            serializer.validated_data["conversation_id"], request.user
        )
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            body_text=serializer.validated_data["body_text"],
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class MarkConversationReadView(APIView):
    """``POST /api/chat/conversations/<id>/read/``: mark the other person's messages as read."""

    @extend_schema(request=None, responses=MarkReadResultSerializer)
    def post(self, request, conversation_id):
        conversation = get_conversation_for_participant(conversation_id, request.user)
        updated = (
            Message.objects.filter(conversation=conversation, read_status=False)
            .exclude(sender=request.user)
            .update(read_status=True)
        )
        return Response({"conversation_id": conversation.pk, "updated_count": updated})
