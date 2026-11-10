"""A small fixed cast of demo accounts (two demo sets), and the code that puts them
back in their starting state before a rehearsal or the showcase.

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
from connections.models import Block, ConnectionRequest, ReferralRequest
from reports.models import Report

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


# Two demo sets, so the two judge panels each start from a fresh demo without a
# reset in between. Each set has a presenter, an alum the presenter already chats
# with, and an alum whose connection request is waiting in the presenter's inbox.
# They are the team's own @ncsu.edu accounts, so the usual sign-in works (a code by
# email), and issue_demo_token signs in without waiting for the email. A reset
# overwrites these accounts' profiles and removes their requests and chats.
#
# Jordan and Lee are fictional and shared by both sets: each presenter can send
# Jordan a fresh request, and Lee is not open to connect. They do not receive mail.


def _presenter(email, first_name, last_name):
    return DemoMember(
        email,
        first_name,
        last_name,
        "Computer Science",
        2027,
        "",
        "",
        "Junior interested in backend and infrastructure work.",
    )


def _red_hat_alum(email, first_name, last_name):
    return DemoMember(
        email,
        first_name,
        last_name,
        "Computer Engineering",
        2024,
        "Software Engineer",
        "Red Hat",
        "Works on platform tooling. Happy to talk about interviews.",
    )


def _sre_alum(email, first_name, last_name):
    return DemoMember(
        email,
        first_name,
        last_name,
        "Computer Science",
        2023,
        "Site Reliability Engineer",
        "Google",
        "On-call veteran. Ask me about SRE internships.",
    )


@dataclass(frozen=True)
class DemoSet:
    label: str
    presenter: DemoMember
    alum: DemoMember  # already chats with the presenter; can be asked for a referral
    waiting: DemoMember  # their connection request is waiting in the presenter's inbox

    @property
    def members(self):
        return (self.presenter, self.alum, self.waiting)


SET_A = DemoSet(
    "A",
    presenter=_presenter("skeshav2@ncsu.edu", "Sameeksha", "Keshav"),
    alum=_red_hat_alum("sshett24@ncsu.edu", "Sanjana", "Shetty"),
    waiting=_sre_alum("rtelgoha@ncsu.edu", "Rawan", "Telgoha"),
)
SET_B = DemoSet(
    "B",
    presenter=_presenter("dbbakalo@ncsu.edu", "Danny", "Bakalov"),
    alum=_red_hat_alum("kmpanick@ncsu.edu", "Karthik", "Panicker"),
    waiting=_sre_alum("tlhart@ncsu.edu", "Thomas", "Hart"),
)
SETS = (SET_A, SET_B)

SAM, AVERY, MAYA = SET_A.members  # set A, which the first panel uses
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
CAST = tuple(member for demo_set in SETS for member in demo_set.members) + (JORDAN, LEE)
CAST_EMAILS = tuple(member.email for member in CAST)
INDUSTRY = {
    "Red Hat": "Software",
    "IBM": "Technology",
    "Google": "Technology",
    "Cisco": "Networking",
}


def demo_user_ids():
    return list(User.objects.filter(email__in=CAST_EMAILS).values_list("pk", flat=True))


def _demo_targets(conversations, ids):
    """Reports are filed against an id, not a foreign key, so say which targets are demo.

    A user target is a demo account; a message target is a message in a demo
    conversation (those messages are deleted with it, which would orphan the report).
    """
    return Q(target_type=Report.TargetType.USER, target_id__in=ids) | Q(
        target_type=Report.TargetType.MESSAGE,
        target_id__in=Message.objects.filter(conversation__in=conversations).values("pk"),
    )


def _scoped_rows(ids):
    """Every row that belongs to the demo accounts, by kind. Nothing else."""
    conversations = Conversation.objects.filter(participants__in=ids).distinct()
    return {
        "conversations": conversations,
        "connection requests": ConnectionRequest.objects.filter(
            Q(sender__in=ids) | Q(recipient__in=ids)
        ),
        "referral requests": ReferralRequest.objects.filter(
            Q(sender__in=ids) | Q(recipient__in=ids)
        ),
        "reports": Report.objects.filter(
            Q(reporter__in=ids) | _demo_targets(conversations, ids)
        ),
        "blocks": Block.objects.filter(Q(blocker__in=ids) | Q(blocked__in=ids)),
        "past roles": PastRole.objects.filter(user__in=ids),
    }


def _with_real_members(kind, queryset, ids):
    """How many of these rows also involve someone who is not a demo account."""
    pairs = {
        "connection requests": ("sender__in", "recipient__in"),
        "referral requests": ("sender__in", "recipient__in"),
        "blocks": ("blocker__in", "blocked__in"),
    }
    if kind in pairs:
        one, two = pairs[kind]
        return queryset.exclude(**{one: ids, two: ids}).count()
    if kind == "reports":
        # Demo-only means a demo reporter and a demo target. A demo account's report
        # about someone else's post or profile, or a real member's report about a
        # demo account, is the kind of overlap worth showing.
        conversations = _scoped_rows(ids)["conversations"]
        demo_only = Q(reporter__in=ids) & _demo_targets(conversations, ids)
        return queryset.exclude(demo_only).count()
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
    # Reports first: one filed against a message is found through the conversation
    # that holds it, so it has to be deleted while that conversation still exists.
    rows["reports"].delete()
    # Conversations next: they outlive a deleted connection request (SET_NULL),
    # so they have to go while the link to them still exists. Messages cascade.
    rows["conversations"].delete()
    for kind in ("connection requests", "referral requests", "blocks", "past roles"):
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


def _build_starting_state(users, demo_set):
    """The state the demo script begins from, for one set.

    The presenter already chats with the alum (so there is a conversation, an
    unread message and a person to ask for a referral), and the other alum is
    waiting in the presenter's inbox (so there is something to accept). Jordan is
    open but unconnected, so the presenter can send a fresh request live, and Lee
    is not open to connect.
    """
    now = timezone.now()
    sam, avery, maya = (users[member.email] for member in demo_set.members)

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
        message_text=(
            f"Hi {sam.first_name}, I saw your profile. Happy to chat about SRE internships."
        ),
    )

    accepted = ConnectionRequest.objects.create(
        sender=sam,
        recipient=avery,
        status=ConnectionRequest.Status.ACCEPTED,
        message_text=f"Hi {avery.first_name}, could we chat about Red Hat?",
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
        for demo_set in SETS:
            _build_starting_state(users, demo_set)
    return users


def remove():
    """Delete the demo accounts and everything of theirs, e.g. after the showcase."""
    with transaction.atomic():
        ids = demo_user_ids()
        _clear(ids)
        deleted, _ = User.objects.filter(pk__in=ids).delete()
    return deleted
