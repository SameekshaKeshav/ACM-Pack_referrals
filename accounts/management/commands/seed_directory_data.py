import sys

from django.core.management.base import BaseCommand, CommandError

from accounts import directory_seed as seed


class Command(BaseCommand):
    help = (
        "Fill the people directory with a browsable set of fictional members "
        f"({len(seed.MEMBERS)} people across {len(seed.COMPANIES)} companies), so the "
        "directory, its filters and the company pages have something in them for the "
        "showcase. Safe to re-run: it only ever touches the accounts it created, which "
        f"are the ones addressed {seed.EMAIL_PREFIX}...{seed.EMAIL_DOMAIN}."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Say what would change; change nothing."
        )
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Delete the seeded people again. Companies are kept.",
        )
        parser.add_argument("--yes", action="store_true", help="Do not ask before deleting.")

    def handle(self, *args, **options):
        found = seed.plan()
        existing = seed.seeded_users().count()

        # Unlike reset_demo_data this needs no environment flag: that one rewrites
        # and can delete the team's own real accounts, while everything here is
        # scoped to addresses this command owns by prefix.
        self.stdout.write(f"Seeded accounts already present: {existing}")
        if options["remove"]:
            self.stdout.write(f"This deletes {existing} seeded people. Companies are kept,")
            self.stdout.write("because real members may since have said they work at one.")
        else:
            for label, count in found.items():
                self.stdout.write(f"  {count:>4}  {label}")
        self.stdout.write("No account outside that prefix is read, changed or deleted.")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: nothing was changed."))
            return

        if options["remove"]:
            if not options["yes"]:
                if not sys.stdin.isatty():
                    raise CommandError("Not a terminal, so cannot ask. Pass --yes to go ahead.")
                if input("Delete the seeded people? [y/N] ").strip().lower() != "y":
                    raise CommandError("Cancelled. Nothing was changed.")
            self.stdout.write(self.style.SUCCESS(f"Removed ({seed.remove()} rows deleted)."))
            return

        users = seed.seed()
        self.stdout.write(
            self.style.SUCCESS(f"Directory seeded: {len(users)} people are now listed.")
        )
        self.stdout.write(
            "Check it at /directory, and try the filters: "
            "?major=Computer%20Science, ?grad_year=2022, and a company page."
        )
