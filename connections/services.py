"""Accept / decline logic for connection requests.

Kept free of HTTP concerns so views can stay thin: each function raises a
``ConnectionActionError`` subclass carrying the HTTP status the view should return.
"""

from django.db import transaction
from django.utils import timezone

from chat.models import Conversation
from chat.services import create_conversation_from_request

from .models import ConnectionRequest


class ConnectionActionError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotRecipientError(ConnectionActionError):
    status_code = 403


class RequestNotPendingError(ConnectionActionError):
    status_code = 409


def _get_pending_for_recipient(connection_id: int, user) -> ConnectionRequest:
    """Lock the request row and check that ``user`` may resolve it.

    Must be called inside ``transaction.atomic()``.

    Raises ``ConnectionRequest.DoesNotExist`` for unknown ids and for users who are
    not part of the request (so its existence is not leaked), ``NotRecipientError``
    for the sender, and ``RequestNotPendingError`` if it was already resolved.
    """
    connection_request = ConnectionRequest.objects.select_for_update().get(pk=connection_id)

    if user.pk not in (connection_request.sender_id, connection_request.recipient_id):
        raise ConnectionRequest.DoesNotExist
    if connection_request.recipient_id != user.pk:
        raise NotRecipientError("Only the recipient can respond to a connection request.")
    if connection_request.status != ConnectionRequest.Status.PENDING:
        raise RequestNotPendingError(
            f"This request is already {connection_request.status}."
        )
    return connection_request


def accept_connection_request(connection_id: int, user) -> tuple[ConnectionRequest, Conversation]:
    """Accept a pending request and create its conversation, atomically.

    If the conversation cannot be created the status change is rolled back.
    """
    with transaction.atomic():
        connection_request = _get_pending_for_recipient(connection_id, user)
        connection_request.status = ConnectionRequest.Status.ACCEPTED
        connection_request.resolved_at = timezone.now()
        connection_request.save(update_fields=["status", "resolved_at"])
        try:
            conversation = create_conversation_from_request(connection_request)
        except ValueError as exc:
            raise RequestNotPendingError(str(exc)) from exc
    return connection_request, conversation


def decline_connection_request(connection_id: int, user) -> ConnectionRequest:
    """Decline a pending request. No conversation is created."""
    with transaction.atomic():
        connection_request = _get_pending_for_recipient(connection_id, user)
        connection_request.status = ConnectionRequest.Status.DECLINED
        connection_request.resolved_at = timezone.now()
        connection_request.save(update_fields=["status", "resolved_at"])
    return connection_request
