import json
import os
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import PastRole, Profile
from api import demo
from chat.models import Conversation, Message
from companies.models import Company
from connections.models import Block, ConnectionRequest, ReferralRequest
from reports.models import Report

User = get_user_model()
ON = {demo.ENV_FLAG: "1"}


def run(command, *args, env=ON, **options):
    """Run a management command with the demo tools switched on (or as given)."""
    out = StringIO()
    with mock.patch.dict(os.environ, env):
        if demo.ENV_FLAG not in env:
            os.environ.pop(demo.ENV_FLAG, None)
        call_command(command, *args, stdout=out, stderr=StringIO(), **options)
    return out.getvalue()


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def real_member(email, company=None):
    user = User.objects.create_user(username=email, email=email, password="not-a-demo")
    Profile.objects.create(
        user=user,
        current_company=company,
        account_status=Profile.AccountStatus.ACTIVE,
        open_to_connect=True,
        major="Math",
    )
    return user


class SwitchTests(TestCase):
    def test_both_commands_refuse_unless_the_flag_is_exactly_1(self):
        for env in ({}, {demo.ENV_FLAG: "0"}, {demo.ENV_FLAG: "true"}, {demo.ENV_FLAG: ""}):
            with self.subTest(env=env):
                with self.assertRaisesRegex(CommandError, "switched off"):
                    run("reset_demo_data", env=env, yes=True)
                with self.assertRaisesRegex(CommandError, "switched off"):
                    run("issue_demo_token", demo.SAM.email, env=env)
        self.assertFalse(User.objects.exists())


class ResetTests(TestCase):
    def test_creates_the_cast_in_the_state_the_demo_starts_from(self):
        run("reset_demo_data", yes=True)

        self.assertEqual(set(User.objects.values_list("email", flat=True)), set(demo.CAST_EMAILS))
        for member in demo.CAST:
            user = User.objects.get(email=member.email)
            self.assertTrue(user.is_active)
            self.assertFalse(user.has_usable_password())
            self.assertEqual(user.profile.account_status, Profile.AccountStatus.ACTIVE)
            self.assertEqual(user.profile.open_to_connect, member.open_to_connect)
        sam = User.objects.get(email=demo.SAM.email)

        # Maya is waiting in Sam's inbox, and Sam already chats with Avery.
        inbox = client_for(sam).get("/api/connections/?type=incoming").json()
        self.assertEqual([row["sender"]["name"] for row in inbox], [demo.MAYA.name])
        conversations = client_for(sam).get("/api/chat/conversations/").json()
        self.assertEqual([c["other_user"]["name"] for c in conversations], [demo.AVERY.name])
        self.assertEqual(conversations[0]["unread_count"], 1)
        thread = (
            client_for(sam)
            .get(f"/api/chat/conversations/{conversations[0]['id']}/messages/")
            .json()
        )
        self.assertEqual(len(thread), 3)
        self.assertEqual(
            [m["created_at"] for m in thread],
            sorted(m["created_at"] for m in thread),
            "messages are in time order",
        )

    def test_everyone_is_in_the_directory_and_lee_is_not_open_to_connect(self):
        run("reset_demo_data", yes=True)
        sam = User.objects.get(email=demo.SAM.email)
        people = client_for(sam).get("/api/accounts/users/").json()["results"]
        self.assertEqual(len(people), len(demo.CAST))
        lee = next(p for p in people if p["name"] == "Lee Park")
        self.assertFalse(lee["open_to_connect"])
        companies = {p["current_company"]["name"] for p in people if p["current_company"]}
        self.assertEqual(companies, {"Red Hat", "IBM", "Google", "Cisco"})

    def test_sam_can_ask_avery_for_a_referral_and_connect_with_jordan_live(self):
        run("reset_demo_data", yes=True)
        sam, avery, jordan = (
            User.objects.get(email=m.email) for m in (demo.SAM, demo.AVERY, demo.JORDAN)
        )
        red_hat = Company.objects.get(name="Red Hat")

        referral = client_for(sam).post(
            "/api/connections/referrals/",
            {
                "recipient_id": avery.pk,
                "company_id": red_hat.pk,
                "role_title": "SWE Intern",
                "contact_email": demo.SAM.email,
                "message_text": "Could you refer me?",
            },
            format="json",
        )
        self.assertEqual(referral.status_code, 201, referral.content)

        connect = client_for(sam).post(
            "/api/connections/",
            {"recipient_id": jordan.pk, "message_text": "Hi Jordan"},
            format="json",
        )
        self.assertEqual(connect.status_code, 201, connect.content)

    def test_running_it_after_a_demo_goes_back_to_the_start(self):
        run("reset_demo_data", yes=True)
        sam, avery, maya, jordan = (
            User.objects.get(email=m.email) for m in (demo.SAM, demo.AVERY, demo.MAYA, demo.JORDAN)
        )
        before = {kind: rows for kind, (rows, _) in demo.plan().items()}

        # A rehearsal: accept Maya, chat with her, ask Avery, connect with Jordan, block and report.
        waiting = ConnectionRequest.objects.get(sender=maya, recipient=sam)
        self.assertEqual(
            client_for(sam).patch(f"/api/connections/{waiting.pk}/accept/").status_code, 200
        )
        client_for(sam).post(
            "/api/chat/messages/",
            {"conversation_id": waiting.conversation.pk, "body_text": "Thanks Maya"},
            format="json",
        )
        client_for(sam).post(
            "/api/connections/", {"recipient_id": jordan.pk, "message_text": "Hi"}, format="json"
        )
        ReferralRequest.objects.create(
            sender=sam, recipient=avery, role_title="SWE", contact_email=sam.email,
            message_text="hi",
        )
        Block.objects.create(blocker=sam, blocked=jordan)
        Report.objects.create(
            reporter=sam,
            target_type=Report.TargetType.USER,
            target_id=jordan.pk,
            reason=Report.Reason.OTHER,
        )
        # A report on a message in a demo conversation: found through that conversation.
        Report.objects.create(
            reporter=maya,
            target_type=Report.TargetType.MESSAGE,
            target_id=Message.objects.filter(conversation=waiting.conversation).first().pk,
            reason=Report.Reason.SPAM,
        )
        PastRole.objects.create(
            user=sam, company=Company.objects.get(name="IBM"), role_title="Intern"
        )
        self.assertNotEqual({k: r for k, (r, _) in demo.plan().items()}, before)
        sam_before = sam.pk

        run("reset_demo_data", yes=True)

        self.assertEqual({k: r for k, (r, _) in demo.plan().items()}, before)
        self.assertEqual(
            User.objects.get(email=demo.SAM.email).pk,
            sam_before,
            "accounts are kept, not recreated",
        )
        self.assertEqual(User.objects.count(), len(demo.CAST))
        inbox = (
            client_for(User.objects.get(email=demo.SAM.email))
            .get("/api/connections/?type=incoming")
            .json()
        )
        self.assertEqual([row["sender"]["name"] for row in inbox], [demo.MAYA.name])
        self.assertEqual(Conversation.objects.count(), 2, "one per demo set")
        self.assertEqual(Message.objects.count(), 6)

    def test_each_demo_set_starts_with_its_own_chat_and_waiting_request(self):
        run("reset_demo_data", yes=True)
        for demo_set in demo.SETS:
            with self.subTest(demo_set=demo_set.label):
                presenter = User.objects.get(email=demo_set.presenter.email)
                inbox = client_for(presenter).get("/api/connections/?type=incoming").json()
                self.assertEqual([row["sender"]["name"] for row in inbox], [demo_set.waiting.name])
                chats = client_for(presenter).get("/api/chat/conversations/").json()
                self.assertEqual([c["other_user"]["name"] for c in chats], [demo_set.alum.name])
                self.assertEqual(chats[0]["unread_count"], 1)

    def test_the_first_panels_demo_does_not_change_the_second_panels_start(self):
        run("reset_demo_data", yes=True)
        sam = User.objects.get(email=demo.SAM.email)
        jordan = User.objects.get(email=demo.JORDAN.email)
        waiting = ConnectionRequest.objects.get(sender__email=demo.MAYA.email, recipient=sam)
        client_for(sam).patch(f"/api/connections/{waiting.pk}/accept/")
        client_for(sam).post(
            "/api/connections/", {"recipient_id": jordan.pk, "message_text": "Hi"}, format="json"
        )

        second = demo.SET_B
        presenter = User.objects.get(email=second.presenter.email)
        inbox = client_for(presenter).get("/api/connections/?type=incoming").json()
        self.assertEqual([row["sender"]["name"] for row in inbox], [second.waiting.name])
        again = client_for(presenter).post(
            "/api/connections/", {"recipient_id": jordan.pk, "message_text": "Hi"}, format="json"
        )
        self.assertEqual(again.status_code, 201, "Jordan is still free for the second presenter")

    def test_the_demo_accounts_are_the_teams_own_ncsu_addresses(self):
        self.assertEqual(
            {member.email for demo_set in demo.SETS for member in demo_set.members},
            {
                "skeshav2@ncsu.edu", "sshett24@ncsu.edu", "rtelgoha@ncsu.edu",
                "dbbakalo@ncsu.edu", "kmpanick@ncsu.edu", "tlhart@ncsu.edu",
            },
        )
        self.assertEqual(len(set(demo.CAST_EMAILS)), len(demo.CAST_EMAILS), "no repeats")

    def test_a_suspended_demo_account_is_active_again_after_a_reset(self):
        run("reset_demo_data", yes=True)
        Profile.objects.filter(user__email=demo.SAM.email).update(
            account_status=Profile.AccountStatus.SUSPENDED
        )
        User.objects.filter(email=demo.SAM.email).update(is_active=False)

        run("reset_demo_data", yes=True)

        sam = User.objects.get(email=demo.SAM.email)
        self.assertTrue(sam.is_active)
        self.assertEqual(sam.profile.account_status, Profile.AccountStatus.ACTIVE)
        self.assertIn("access token", run("issue_demo_token", demo.SAM.email))

    def test_profile_edits_to_a_demo_account_are_put_back(self):
        run("reset_demo_data", yes=True)
        Profile.objects.filter(user__email=demo.AVERY.email).update(
            current_role="Intern", open_to_connect=False, bio="vandalised", current_company=None
        )
        User.objects.filter(email=demo.AVERY.email).update(first_name="Nobody")

        run("reset_demo_data", yes=True)

        avery = User.objects.get(email=demo.AVERY.email)
        self.assertEqual(avery.first_name, demo.AVERY.first_name)
        self.assertEqual(avery.profile.current_role, "Software Engineer")
        self.assertEqual(avery.profile.current_company.name, "Red Hat")
        self.assertTrue(avery.profile.open_to_connect)

    def test_real_members_and_their_data_are_left_alone(self):
        acme = Company.objects.create(name="Acme")
        ana, ben = real_member("ana@ncsu.edu", acme), real_member("ben@ncsu.edu", acme)
        PastRole.objects.create(user=ana, company=acme, role_title="Intern")
        between_them = ConnectionRequest.objects.create(
            sender=ana, recipient=ben, status=ConnectionRequest.Status.ACCEPTED
        )
        talk = Conversation.objects.create(created_from_connection_request=between_them)
        talk.participants.add(ana, ben)
        Message.objects.create(conversation=talk, sender=ana, body_text="private")
        Report.objects.create(
            reporter=ana,
            target_type=Report.TargetType.USER,
            target_id=ben.pk,
            reason=Report.Reason.OTHER,
        )
        Report.objects.create(
            reporter=ben,
            target_type=Report.TargetType.MESSAGE,
            target_id=Message.objects.get(conversation=talk).pk,
            reason=Report.Reason.OTHER,
        )
        Block.objects.create(blocker=ben, blocked=ana)
        ReferralRequest.objects.create(
            sender=ana, recipient=ben, role_title="SWE", contact_email=ana.email,
            message_text="x", company=acme,
        )
        snapshot = (
            list(User.objects.filter(pk__in=[ana.pk, ben.pk]).values()),
            list(Profile.objects.filter(user__in=[ana, ben]).values()),
            Message.objects.filter(conversation=talk).count(),
        )

        run("reset_demo_data", yes=True)
        run("reset_demo_data", yes=True)

        self.assertEqual(
            snapshot,
            (
                list(User.objects.filter(pk__in=[ana.pk, ben.pk]).values()),
                list(Profile.objects.filter(user__in=[ana, ben]).values()),
                Message.objects.filter(conversation=talk).count(),
            ),
        )
        self.assertTrue(ConnectionRequest.objects.filter(pk=between_them.pk).exists())
        self.assertEqual(Report.objects.filter(reporter__in=[ana, ben]).count(), 2)
        self.assertTrue(Block.objects.filter(blocker=ben).exists())
        self.assertTrue(ReferralRequest.objects.filter(sender=ana).exists())
        self.assertTrue(PastRole.objects.filter(user=ana).exists())
        self.assertEqual(Company.objects.filter(name="Acme").count(), 1)

    def test_a_real_member_who_tried_a_demo_account_loses_only_that_link_and_the_plan_says_so(self):
        run("reset_demo_data", yes=True)
        ana = real_member("ana@ncsu.edu")
        avery = User.objects.get(email=demo.AVERY.email)
        stray = ConnectionRequest.objects.create(
            sender=ana, recipient=avery, status=ConnectionRequest.Status.ACCEPTED
        )
        talk = Conversation.objects.create(created_from_connection_request=stray)
        talk.participants.add(ana, avery)

        report = run("reset_demo_data", dry_run=True)
        self.assertRegex(report, r"1 with a real member")
        self.assertTrue(
            ConnectionRequest.objects.filter(pk=stray.pk).exists(), "a dry run deletes nothing"
        )

        run("reset_demo_data", yes=True)
        self.assertFalse(ConnectionRequest.objects.filter(pk=stray.pk).exists())
        self.assertFalse(Conversation.objects.filter(pk=talk.pk).exists())
        self.assertTrue(User.objects.filter(pk=ana.pk).exists())
        self.assertTrue(Profile.objects.filter(user=ana).exists())

    def test_reports_about_demo_people_and_demo_messages_are_cleared_and_counted(self):
        run("reset_demo_data", yes=True)
        ana = real_member("ana@ncsu.edu")
        other = real_member("other@ncsu.edu")
        avery = User.objects.get(email=demo.AVERY.email)
        demo_message = Message.objects.filter(conversation__participants=avery).first()
        about_demo_user = Report.objects.create(
            reporter=ana,
            target_type=Report.TargetType.USER,
            target_id=avery.pk,
            reason=Report.Reason.SPAM,
        )
        about_demo_message = Report.objects.create(
            reporter=ana,
            target_type=Report.TargetType.MESSAGE,
            target_id=demo_message.pk,
            reason=Report.Reason.SPAM,
        )
        # Same numbers as the demo ids, but about real people: must survive.
        about_real_user = Report.objects.create(
            reporter=ana,
            target_type=Report.TargetType.USER,
            target_id=other.pk,
            reason=Report.Reason.SPAM,
        )

        report = run("reset_demo_data", dry_run=True)
        self.assertRegex(report, r"2\s+reports\s+\(2 with a real member\)")

        run("reset_demo_data", yes=True)
        self.assertFalse(Report.objects.filter(pk=about_demo_user.pk).exists())
        self.assertFalse(Report.objects.filter(pk=about_demo_message.pk).exists())
        self.assertTrue(Report.objects.filter(pk=about_real_user.pk).exists())

    def test_dry_run_changes_nothing_and_reports_the_counts(self):
        self.assertIn("Dry run: nothing was changed", run("reset_demo_data", dry_run=True))
        self.assertFalse(User.objects.exists())

        run("reset_demo_data", yes=True)
        snapshot = (
            User.objects.count(),
            ConnectionRequest.objects.count(),
            Message.objects.count(),
        )
        report = run("reset_demo_data", dry_run=True)
        self.assertIn("connection requests", report)
        self.assertIn("messages", report)
        self.assertEqual(
            snapshot,
            (User.objects.count(), ConnectionRequest.objects.count(), Message.objects.count()),
        )

    def test_it_will_not_go_ahead_without_yes_when_there_is_no_terminal(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaisesRegex(CommandError, "Pass --yes"):
                run("reset_demo_data")
        self.assertFalse(User.objects.exists())

    def test_at_a_terminal_anything_but_y_cancels(self):
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
            "builtins.input", return_value="n"
        ):
            with self.assertRaisesRegex(CommandError, "Cancelled"):
                run("reset_demo_data")
        self.assertFalse(User.objects.exists())
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
            "builtins.input", return_value="y"
        ):
            run("reset_demo_data")
        self.assertEqual(User.objects.count(), len(demo.CAST))

    def test_it_refuses_to_take_over_a_staff_account_at_a_demo_address(self):
        User.objects.create_superuser(username="admin", email=demo.SAM.email, password="x")
        with self.assertRaisesRegex(CommandError, "staff account"):
            run("reset_demo_data", yes=True)
        self.assertTrue(User.objects.get(email=demo.SAM.email).is_superuser)
        self.assertEqual(User.objects.count(), 1, "nothing else was created either")

    def test_remove_refuses_a_cast_account_that_became_staff_and_deletes_nothing(self):
        run("reset_demo_data", yes=True)
        User.objects.filter(email=demo.SAM.email).update(is_superuser=True, is_staff=True)
        before = (User.objects.count(), ConnectionRequest.objects.count(), Message.objects.count())

        with self.assertRaisesRegex(CommandError, "staff account"):
            run("reset_demo_data", yes=True, remove=True)

        self.assertTrue(User.objects.get(email=demo.SAM.email).is_superuser)
        self.assertEqual(
            before,
            (User.objects.count(), ConnectionRequest.objects.count(), Message.objects.count()),
        )

    def test_a_failure_part_way_leaves_nothing_half_done(self):
        run("reset_demo_data", yes=True)
        before = (User.objects.count(), ConnectionRequest.objects.count(), Message.objects.count())
        with mock.patch.object(demo, "_build_starting_state", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                run("reset_demo_data", yes=True)
        self.assertEqual(
            before,
            (User.objects.count(), ConnectionRequest.objects.count(), Message.objects.count()),
        )

    def test_remove_deletes_the_demo_accounts_and_only_those(self):
        ana = real_member("ana@ncsu.edu")
        run("reset_demo_data", yes=True)
        self.assertEqual(User.objects.count(), len(demo.CAST) + 1)

        run("reset_demo_data", yes=True, remove=True)

        self.assertEqual(list(User.objects.values_list("email", flat=True)), [ana.email])
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)
        self.assertTrue(Profile.objects.filter(user=ana).exists())


class IssueTokenTests(TestCase):
    def setUp(self):
        run("reset_demo_data", yes=True)

    def session_from(self, output):
        prefix = "localStorage.setItem("
        line = next(row for row in output.splitlines() if row.startswith(prefix))
        arguments = line[len(prefix):line.index("); location")]
        key, value = json.loads("[" + arguments + "]")
        return key, json.loads(value)

    def test_the_printed_login_works_against_the_api_as_that_account(self):
        output = run("issue_demo_token", demo.SAM.email)
        key, session = self.session_from(output)

        self.assertEqual(key, "pack-referrals.session.v1")
        sam = User.objects.get(email=demo.SAM.email)
        self.assertEqual(session["user"], {"id": sam.pk, "email": demo.SAM.email})
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {session['access']}")
        me = client.get("/api/accounts/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], demo.SAM.email)
        refreshed = APIClient().post(
            "/api/accounts/auth/refresh/", {"refresh": session["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, 200)

    def test_the_address_is_matched_ignoring_case_and_spaces(self):
        self.assertIn(
            demo.SAM.name, run("issue_demo_token", f"  {demo.SAM.email.upper()} ")
        )

    def test_it_never_issues_a_login_for_a_real_member_or_an_admin(self):
        ana = real_member("ana@ncsu.edu")
        admin = User.objects.create_superuser(username="boss", email="boss@ncsu.edu", password="x")
        for target in (ana, admin, "nobody@gmail.com"):
            email = target if isinstance(target, str) else target.email
            with self.subTest(email=email):
                with self.assertRaisesRegex(CommandError, "Only the demo accounts"):
                    run("issue_demo_token", email)

    def test_it_says_what_to_do_when_the_demo_accounts_do_not_exist_yet(self):
        run("reset_demo_data", yes=True, remove=True)
        with self.assertRaisesRegex(CommandError, "reset_demo_data"):
            run("issue_demo_token", demo.SAM.email)

    def test_a_suspended_demo_account_gets_no_login(self):
        Profile.objects.filter(user__email=demo.SAM.email).update(
            account_status=Profile.AccountStatus.SUSPENDED
        )
        with self.assertRaisesRegex(CommandError, "does not exist yet"):
            run("issue_demo_token", demo.SAM.email)

    def test_it_refuses_a_cast_account_that_became_staff(self):
        User.objects.filter(email=demo.SAM.email).update(is_staff=True)
        with self.assertRaisesRegex(CommandError, "staff account"):
            run("issue_demo_token", demo.SAM.email)

    def test_the_output_gives_the_access_and_the_refresh_lifetimes(self):
        output = run("issue_demo_token", demo.SAM.email)
        self.assertIn("access token is valid for about 24 hours", output)
        self.assertIn("refresh token printed with it for up to 7 days", output)

    def test_the_output_warns_that_the_login_is_a_password(self):
        output = run("issue_demo_token", demo.SAM.email)
        self.assertIn("Treat it like a password", output)
