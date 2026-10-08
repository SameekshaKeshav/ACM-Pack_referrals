from django.db import IntegrityError, transaction

from connections.models import ConnectionRequest

from .models import Conversation, ConversationParticipant

ALREADY_EXISTS_MESSAGE = "A conversation already exists for this connection request."


def create_conversation_from_request(connection_request: ConnectionRequest) -> Conversation:
    """
    Open a 1:1 conversation for an accepted connection request.

    Creates one Conversation and two ConversationParticipant rows (sender + recipient).

    Raises ValueError (and only ValueError) when the request cannot open a
    conversation: it is not accepted, sender and recipient are the same user, or a
    conversation already exists - including when two accepts race each other.
    """
    if connection_request.status != ConnectionRequest.Status.ACCEPTED:
        raise ValueError(
            "Connection request must be accepted before creating a conversation."
        )

    if connection_request.sender_id == connection_request.recipient_id:
        raise ValueError("Cannot create a conversation with yourself.")

    if Conversation.objects.filter(
        created_from_connection_request=connection_request
    ).exists():
        raise ValueError(ALREADY_EXISTS_MESSAGE)

    try:
        with transaction.atomic():
            conversation = Conversation.objects.create(
                created_from_connection_request=connection_request,
            )
            ConversationParticipant.objects.bulk_create(
                [
                    ConversationParticipant(
                        conversation=conversation,
                        user=connection_request.sender,
                    ),
                    ConversationParticipant(
                        conversation=conversation,
                        user=connection_request.recipient,
                    ),
                ]
            )
    except IntegrityError as exc:
        # The exists() check above is not atomic with the insert, so a concurrent
        # accept can slip past it. The one-to-one constraint rejects the loser;
        # surface that as the same ValueError a sequential duplicate gets.
        raise ValueError(ALREADY_EXISTS_MESSAGE) from exc

    return conversation
