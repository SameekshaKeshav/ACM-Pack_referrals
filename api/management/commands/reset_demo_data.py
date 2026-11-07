import sys

from django.core.management.base import BaseCommand, CommandError

from api import demo


class Command(BaseCommand):
    help = (
        "Put the five demo accounts (demo.sam@ncsu.edu and friends) back to the state "
        "the showcase demo starts from. Touches only those accounts. "
        "Needs ALLOW_DEMO_TOOLS=1."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Show what would be deleted; change nothing."
        )
        parser.add_argument(
            "--yes", action="store_true", help="Do not ask before changing anything."
        )
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Delete the demo accounts entirely (for after the showcase), not reset them.",
        )

    def handle(self, *args, **options):
        demo.require_demo_tools()
        found = demo.plan()
        total = sum(rows for rows, _ in found.values())

        self.stdout.write("Demo accounts: " + ", ".join(demo.CAST_EMAILS))
        self.stdout.write(
            f"This {'removes the accounts and ' if options['remove'] else ''}deletes:"
        )
        for kind, (rows, with_real) in found.items():
            extra = f"  ({with_real} with a real member)" if with_real else ""
            self.stdout.write(f"  {rows:>4}  {kind}{extra}")
        if not options["remove"]:
            self.stdout.write(
                "then recreates the starting state: 5 accounts, 1 conversation, 1 request waiting."
            )
        self.stdout.write("No other member's profile or data is touched.")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: nothing was changed."))
            return
        if not options["yes"]:
            if not sys.stdin.isatty():
                raise CommandError("Not a terminal, so cannot ask. Pass --yes to go ahead.")
            if input("Go ahead? [y/N] ").strip().lower() != "y":
                raise CommandError("Cancelled. Nothing was changed.")

        if options["remove"]:
            demo.remove()
            self.stdout.write(self.style.SUCCESS("Demo accounts removed."))
            return
        demo.reset()
        self.stdout.write(self.style.SUCCESS(f"Demo data reset ({total} rows cleared)."))
        self.stdout.write(
            "Sign in as the presenter with: "
            f"ALLOW_DEMO_TOOLS=1 python manage.py issue_demo_token {demo.SAM.email}"
        )
