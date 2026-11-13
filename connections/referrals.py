"""Rules for referral requests, kept free of HTTP so they can be tested directly.

A referral ask may only go to someone the sender is already connected to: an accepted
``ConnectionRequest`` between the two, in either direction. Each function raises a
``ReferralError`` subclass carrying the HTTP status the view should return.
"""

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import PastRole, Profile

from .blocks import blocked_user_ids
from .models import ConnectionRequest, ReferralRequest


class ReferralError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class ReferralNotAllowedError(ReferralError):
    status_code = 403


class DuplicateReferralError(ReferralError):
    status_code = 409


class NotReferralRecipientError(ReferralError):
    status_code = 403


class ReferralNotPendingError(ReferralError):
    status_code = 409


def are_connected(user, other) -> bool:
    """True if ``user`` and ``other`` have an accepted connection, in either direction."""
    return ConnectionRequest.objects.filter(
        Q(sender=user, recipient=other) | Q(sender=other, recipient=user),
        status=ConnectionRequest.Status.ACCEPTED,
    ).exists()


def company_ids_on_profile(user) -> set[int]:
    """Companies on ``user``'s profile: where they work now plus every past role."""
    ids = set(
        PastRole.objects.filter(user=user).values_list("company_id", flat=True)
    )
    current = (
        Profile.objects.filter(user=user)
        .values_list("current_company_id", flat=True)
        .first()
    )
    if current is not None:
        ids.add(current)
    return ids


def check_may_ask(sender, recipient) -> None:
    """Raise ``ReferralNotAllowedError`` unless ``sender`` may ask ``recipient``.

    The sender must have an active account: a suspended member whose token is
    still valid must not be able to keep sending asks. That refusal is about the
    caller's own account, so it has its own message.

    Every refusal about the other person shares one message, so it does not reveal
    whether they blocked you or have been suspended.
    """
    sender_profile = getattr(sender, "profile", None)
    if sender_profile is None or sender_profile.account_status != Profile.AccountStatus.ACTIVE:
        raise ReferralNotAllowedError(
            "Your account must be active to ask for a referral."
        )
    refusal = ReferralNotAllowedError(
        "You can only ask someone you are connected to for a referral."
    )
    if sender.pk == recipient.pk:
        raise ReferralError("You cannot ask yourself for a referral.")
    if not are_connected(sender, recipient):
        raise refusal
    if recipient.pk in blocked_user_ids(sender):
        raise refusal
    profile = getattr(recipient, "profile", None)
    if profile is None or profile.account_status != Profile.AccountStatus.ACTIVE:
        raise refusal


def create_referral_request(sender, recipient, *, company, role_title, contact_email,
                            job_url, resume_url, message_text) -> ReferralRequest:
    """Create a pending ask, or raise if one for the same role is already open.

    The same person, company and role (ignoring case) cannot have two pending asks.
    The unique constraints on the model compare the role case-insensitively too, so
    they catch two simultaneous requests that both pass the read below, however
    each one capitalised the role.
    """
    duplicates = ReferralRequest.objects.filter(
        sender=sender,
        recipient=recipient,
        status=ReferralRequest.Status.PENDING,
        role_title__iexact=role_title,
    )
    duplicates = duplicates.filter(company=company) if company else duplicates.filter(
        company__isnull=True
    )
    already_open = DuplicateReferralError(
        "You already have a pending referral request for this role."
    )
    if duplicates.exists():
        raise already_open

    try:
        with transaction.atomic():
            return ReferralRequest.objects.create(
                sender=sender,
                recipient=recipient,
                company=company,
                role_title=role_title,
                contact_email=contact_email,
                job_url=job_url,
                resume_url=resume_url,
                message_text=message_text,
            )
    except IntegrityError as exc:
        raise already_open from exc


def _answerable_referrals(user):
    """Referral asks ``user`` may act on: their own, minus anyone blocked.

    The same set the detail endpoint shows. Answering something you cannot
    read would be the odd behaviour, so a block hides an ask from accept and
    decline exactly as it hides it from GET. This is the one place referrals
    are stricter than connection accept/decline, which do not consider blocks.
    """
    blocked = blocked_user_ids(user)
    return (
        ReferralRequest.objects.filter(Q(sender=user) | Q(recipient=user))
        .exclude(sender_id__in=blocked)
        .exclude(recipient_id__in=blocked)
    )


def _get_referral_for_recipient(referral_id: int, user) -> ReferralRequest:
    """Load the ask and check that ``user`` may answer it.

    Raises ``ReferralRequest.DoesNotExist`` for unknown ids and for anyone not
    party to the ask, so one response covers both and the existence of someone
    else's ask is never leaked. The sender gets ``NotReferralRecipientError``
    (403), because they can already see it and the refusal tells them nothing
    new. An already-answered ask raises ``ReferralNotPendingError`` (409).

    A plain read, before the write transaction. The pending check is repeated
    atomically in ``_resolve_referral``, which is what makes it safe.
    """
    referral = _answerable_referrals(user).get(pk=referral_id)

    if referral.recipient_id != user.pk:
        raise NotReferralRecipientError(
            "Only the recipient can respond to a referral request."
        )
    if referral.status != ReferralRequest.Status.PENDING:
        raise ReferralNotPendingError(f"This request is already {referral.status}.")
    return referral


def _resolve_referral(referral: ReferralRequest, new_status: str) -> None:
    """Move a pending ask to ``new_status``, or raise if someone else got there first.

    One conditional ``UPDATE ... WHERE status = 'pending'`` and a row count, so
    exactly one of two simultaneous calls wins and the other gets a 409. This
    is deliberately not ``select_for_update()``, which does nothing on SQLite
    (``has_select_for_update`` is False) and so would look correct while
    locking nothing. Mirrors ``services._resolve`` for connections.
    """
    resolved_at = timezone.now()
    updated = ReferralRequest.objects.filter(
        pk=referral.pk, status=ReferralRequest.Status.PENDING
    ).update(status=new_status, resolved_at=resolved_at)
    if updated == 0:
        raise ReferralNotPendingError("This request has already been answered.")
    referral.status = new_status
    referral.resolved_at = resolved_at


def answer_referral_request(referral_id: int, user, new_status: str) -> ReferralRequest:
    """Accept or decline a pending ask on the recipient's behalf.

    Nothing else happens: the two already have a conversation (that is a
    precondition of asking), so unlike a connection accept there is no
    conversation to create. Notification emails are deliberately not sent.
    """
    referral = _get_referral_for_recipient(referral_id, user)
    with transaction.atomic():
        _resolve_referral(referral, new_status)
    return referral
