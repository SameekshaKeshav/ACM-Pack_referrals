"""A small fixed cast of demo accounts, and the code that puts them back in their
starting state before a rehearsal or the showcase.

Why this is careful: the commands built on this run against staging, where real
ACM members have real data. So everything here is scoped to the people in CAST
(identified by e-mail address) and never touches anyone else's profile, past
roles or messages. The one unavoidable overlap is a conversation, connection
request or referral between a demo account and a real member, for example when
someone tries the app on a demo account. Those rows are deleted with the demo
account's other rows, and the plan counts them separately so nobody is surprised.

Nothing here runs unless ALLOW_DEMO_TOOLS=1 is set for that one command.
"""

import os
from dataclasses import dataclass
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import PastRole, Profile
from chat.models import Conversation, Message
from chat.services import create_conversation_from_request
from companies.models import Company
from connections.models import Block, ConnectionRequest, ReferralRequest, Report

User = get_user_model()

ENV_FLAG = "ALLOW_DEMO_TOOLS"


def require_demo_tools():
    """Refuse to run unless the environment says these tools are allowed."""
    if os.environ.get(ENV_FLAG) != "1":
        raise CommandError(
            f"Demo tools are switched off. Set {ENV_FLAG}=1 for this command, "
            f"for example: {ENV_FLAG}=1 python manage.py reset_demo_data. "
            "Leave it unset the rest of the time."
        )


@dataclass(frozen=True)
class DemoMember:
    email: str
    first_name: str
    last_name: str
    major: str
    grad_year: int
    role: str
    company: str  # "" for a student with no company yet
    bio: str
    open_to_connect: bool = True

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"


# The presenter signs in as Sam. Everyone else is someone Sam meets in the demo.
# These addresses are on the allowed signup domain so the normal sign-in rules
# accept them, but they do not receive mail: use issue_demo_token to sign in.
SAM = DemoMember(
    "demo.sam@ncsu.edu",
    "Sam",
    "Student",
    "Computer Science",
    2027,
    "",
    "",
    "Junior interested in backend and infrastructure work.",
)
AVERY = DemoMember(
    "demo.avery@ncsu.edu",
    "Avery",
    "Chen",
    "Computer Engineering",
    2024,
    "Software Engineer",
    "Red Hat",
    "Works on platform tooling. Happy to talk about interviews.",
)
JORDAN = DemoMember(
    "demo.jordan@ncsu.edu",
    "Jordan",
    "Diaz",
    "Statistics",
    2025,
    "Data Analyst",
    "IBM",
    "Analytics and experimentation.",
)
MAYA = DemoMember(
    "demo.maya@ncsu.edu",
    "Maya",
    "Patel",
    "Computer Science",
    2023,
    "Site Reliability Engineer",
    "Google",
    "On-call veteran. Ask me about SRE internships.",
)
LEE = DemoMember(
    "demo.lee@ncsu.edu",
    "Lee",
    "Park",
    "Electrical Engineering",
    2025,
    "Hardware Engineer",
    "Cisco",
    "Not taking new connections right now.",
    open_to_connect=False,
)
CAST = (SAM, AVERY, JORDAN, MAYA, LEE)
CAST_EMAILS = tuple(member.email for member in CAST)
INDUSTRY = {
    "Red Hat": "Software",
    "IBM": "Technology",
    "Google": "Technology",
    "Cisco": "Networking",
}


def demo_user_ids():
    return list(User.objects.filter(email__in=CAST_EMAILS).values_list("pk", flat=True))


def _scoped_rows(ids):
    """Every row that belongs to the demo accounts, by kind. Nothing else."""
    return {
        "conversations": Conversation.objects.filter(participants__in=ids).distinct(),
        "connection requests": ConnectionRequest.objects.filter(
            Q(sender__in=ids) | Q(recipient__in=ids)
        ),
        "referral requests": ReferralRequest.objects.filter(
            Q(sender__in=ids) | Q(recipient__in=ids)
        ),
        "reports": Report.objects.filter(Q(reporter__in=ids) | Q(reported_user__in=ids)),
        "blocks": Block.objects.filter(Q(blocker__in=ids) | Q(blocked__in=ids)),
        "past roles": PastRole.objects.filter(user__in=ids),
    }


def _with_real_members(kind, queryset, ids):
    """How many of these rows also involve someone who is not a demo account."""
    pairs = {
        "connection requests": ("sender__in", "recipient__in"),
        "referral requests": ("sender__in", "recipient__in"),
        "reports": ("reporter__in", "reported_user__in"),
        "blocks": ("blocker__in", "blocked__in"),
    }
    if kind in pairs:
        one, two = pairs[kind]
        return queryset.exclude(**{one: ids, two: ids}).count()
    if kind == "conversations":
        wanted = set(ids)
        return sum(
            1
            for conversation in queryset
            if set(conversation.participants.values_list("pk", flat=True)) - wanted
        )
    return 0


def plan():
    """What a reset would delete: {kind: (rows, of_which_involve_real_members)}."""
    ids = demo_user_ids()
    found = {}
    for kind, queryset in _scoped_rows(ids).items():
        found[kind] = (queryset.count(), _with_real_members(kind, queryset, ids))
    messages = Message.objects.filter(conversation__in=_scoped_rows(ids)["conversations"]).count()
    found["messages"] = (messages, 0)
    return found


def _clear(ids):
    rows = _scoped_rows(ids)
    # Conversations first: they outlive a deleted connection request (SET_NULL),
    # so they have to go while the link to them still exists. Messages cascade.
    rows["conversations"].delete()
    for kind in ("connection requests", "referral requests", "reports", "blocks", "past roles"):
        rows[kind].delete()


def _company(name):
    company, created = Company.find_or_create(name)
    if created and name in INDUSTRY:
        company.industry_tag = INDUSTRY[name]
        company.save(update_fields=["industry_tag"])
    return company


def _ensure_member(member):
    existing = User.objects.filter(email__iexact=member.email).first()
    if existing is not None and (existing.is_staff or existing.is_superuser):
        raise CommandError(
            f"{member.email} already belongs to a staff account. "
            "Refusing to turn it into a demo account."
        )
    user = existing or User(username=member.email, email=member.email)
    if existing is None:
        user.set_unusable_password()  # sign-in is by emailed code, or issue_demo_token
    user.email = member.email
    user.first_name, user.last_name = member.first_name, member.last_name
    user.is_active = True
    user.save()
    Profile.objects.update_or_create(
        user=user,
        defaults={
            "major": member.major,
            "grad_year": member.grad_year,
            "bio": member.bio,
            "current_role": member.role,
            "current_company": _company(member.company) if member.company else None,
            "open_to_connect": member.open_to_connect,
            "account_status": Profile.AccountStatus.ACTIVE,
            "verified_via": Profile.VerifiedVia.NCSU_EMAIL,
        },
    )
    return user


def _stamp(model, pk, field, moment):
    """Set a timestamp that auto_now_add would otherwise pin to 'now'."""
    model.objects.filter(pk=pk).update(**{field: moment})


def _build_starting_state(users):
    """The state the demo script begins from.

    Sam already chats with Avery (so there is a conversation, an unread message
    and a person to ask for a referral), and Maya is waiting in Sam's inbox
    (so there is something to accept). Jordan is open but unconnected, so Sam
    can send a fresh request live, and Lee is not open to connect.
    """
    now = timezone.now()
    sam, avery, maya = users[SAM.email], users[AVERY.email], users[MAYA.email]

    ibm = _company("IBM")
    PastRole.objects.create(
        user=avery,
        company=ibm,
        role_title="Software Engineering Intern",
        start_date=date(2022, 5, 16),
        end_date=date(2022, 8, 5),
    )

    ConnectionRequest.objects.create(
        sender=maya,
        recipient=sam,
        status=ConnectionRequest.Status.PENDING,
        message_text="Hi Sam, I saw your profile. Happy to chat about SRE internships.",
    )

    accepted = ConnectionRequest.objects.create(
        sender=sam,
        recipient=avery,
        status=ConnectionRequest.Status.ACCEPTED,
        message_text="Hi Avery, could we chat about Red Hat?",
    )
    _stamp(ConnectionRequest, accepted.pk, "created_at", now - timedelta(days=3))
    _stamp(ConnectionRequest, accepted.pk, "resolved_at", now - timedelta(days=3, minutes=-30))
    conversation = create_conversation_from_request(accepted)
    script = (
        (avery, "Welcome! Happy to answer questions about Red Hat.", True, timedelta(days=2)),
        (
            sam,
            "Thanks! What was the interview process like for you?",
            True,
            timedelta(days=2, minutes=-10),
        ),
        (
            avery,
            "Two technical rounds and one on team fit. Ask me anything.",
            False,
            timedelta(hours=3),
        ),
    )
    for sender, body, read, age in script:
        message = Message.objects.create(
            conversation=conversation, sender=sender, body_text=body, read_status=read
        )
        _stamp(Message, message.pk, "created_at", now - age)


def reset():
    """Put the demo accounts back to their starting state. Returns the users by email."""
    with transaction.atomic():
        _clear(demo_user_ids())
        users = {member.email: _ensure_member(member) for member in CAST}
        _build_starting_state(users)
    return users


def remove():
    """Delete the demo accounts and everything of theirs, e.g. after the showcase."""
    with transaction.atomic():
        ids = demo_user_ids()
        _clear(ids)
        deleted, _ = User.objects.filter(pk__in=ids).delete()
    return deleted
