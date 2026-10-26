"""Accept / decline logic for connection requests.

Kept free of HTTP concerns so views can stay thin: each function raises a
``ConnectionActionError`` subclass carrying the HTTP status the view should return.

Resolving a request is a single conditional ``UPDATE ... WHERE status = 'pending'``
and a row count, so exactly one of two simultaneous accept/decline calls wins and
the other gets a 409. That holds on SQLite (where ``select_for_update()`` does
nothing) and on Postgres alike.
"""

from django.db import transaction
from django.utils import timezone

from chat.models import Conversation
from chat.services import ConversationAlreadyExistsError, create_conversation_from_request

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


def _get_request_for_recipient(connection_id: int, user) -> ConnectionRequest:
    """Load the request and check that ``user`` may resolve it.

    Raises ``ConnectionRequest.DoesNotExist`` for unknown ids and for users who are
    not part of the request (so its existence is not leaked), ``NotRecipientError``
    for the sender, and ``RequestNotPendingError`` if it was already resolved.

    This is a plain read, done before the write transaction starts. The check that
    the request is still pending is repeated atomically in ``_resolve``.
    """
    connection_request = ConnectionRequest.objects.get(pk=connection_id)

    if user.pk not in (connection_request.sender_id, connection_request.recipient_id):
        raise ConnectionRequest.DoesNotExist
    if connection_request.recipient_id != user.pk:
        raise NotRecipientError("Only the recipient can respond to a connection request.")
    if connection_request.status != ConnectionRequest.Status.PENDING:
        raise RequestNotPendingError(
            f"This request is already {connection_request.status}."
        )
    return connection_request


def _resolve(connection_request: ConnectionRequest, new_status: str) -> None:
    """Move a pending request to ``new_status``, or raise if someone else got there first.

    Must be called inside ``transaction.atomic()``; it is the first write, so on SQLite
    the write lock is taken here rather than upgraded from an earlier read.
    """
    resolved_at = timezone.now()
    updated = ConnectionRequest.objects.filter(
        pk=connection_request.pk, status=ConnectionRequest.Status.PENDING
    ).update(status=new_status, resolved_at=resolved_at)
    if updated == 0:
        raise RequestNotPendingError("This request has already been resolved.")
    connection_request.status = new_status
    connection_request.resolved_at = resolved_at


def accept_connection_request(connection_id: int, user) -> tuple[ConnectionRequest, Conversation]:
    """Accept a pending request and create its conversation, atomically.

    If the conversation cannot be created the status change is rolled back.
    """
    connection_request = _get_request_for_recipient(connection_id, user)
    with transaction.atomic():
        _resolve(connection_request, ConnectionRequest.Status.ACCEPTED)
        try:
            conversation = create_conversation_from_request(connection_request)
        except ConversationAlreadyExistsError as exc:
            raise RequestNotPendingError(str(exc)) from exc
        except ValueError as exc:
            # Not a conflict: the request itself cannot open a conversation (for
            # example a request to yourself, which the API blocks but admin or a
            # seed command could create).
            raise ConnectionActionError(str(exc)) from exc
    return connection_request, conversation


def decline_connection_request(connection_id: int, user) -> ConnectionRequest:
    """Decline a pending request. No conversation is created."""
    connection_request = _get_request_for_recipient(connection_id, user)
    with transaction.atomic():
        _resolve(connection_request, ConnectionRequest.Status.DECLINED)
    return connection_request
