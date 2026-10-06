from django.db import transaction

from connections.models import ConnectionRequest

from .models import Conversation, ConversationParticipant


def create_conversation_from_request(connection_request: ConnectionRequest) -> Conversation:
    """
    Open a 1:1 conversation for an accepted connection request.

    Creates one Conversation and two ConversationParticipant rows (sender + recipient).
    """
    if connection_request.status != ConnectionRequest.Status.ACCEPTED:
        raise ValueError(
            "Connection request must be accepted before creating a conversation."
        )

    if Conversation.objects.filter(
        created_from_connection_request=connection_request
    ).exists():
        raise ValueError("A conversation already exists for this connection request.")

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

    return conversation
