"""A directory full enough to browse: ~20 companies and the people at them.

The demo's directory, filters and company pages are only convincing with a
populated directory, and seed_demo_data makes three accounts for API tests.
This fills the rest in.

Why this is safe to run on staging, where real members have real data: every
account it creates is addressed ``seed.<something>@ncsu.edu``, and it only ever
reads, writes or deletes rows belonging to those addresses. The prefix cannot
collide with a real address, because a real one is a Unity ID and a Unity ID has
no dot in it. Nothing else is touched, and running it twice leaves the same
state as running it once.

These people are fictional. They are ACTIVE so the directory shows them (it
hides everyone else), but nobody can sign in as them: their passwords are
unusable and their addresses have no inbox. Do not request a login code for one
- the email would bounce and spend part of the day's Brevo budget.
"""

from dataclasses import dataclass
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction

from companies.models import Company

from .models import PastRole, Profile

User = get_user_model()

EMAIL_PREFIX = "seed."
EMAIL_DOMAIN = "@ncsu.edu"

# Research Triangle employers, the ones an NC State alum plausibly works at, plus
# the national names our members actually intern with. The industry tag is what
# the company page shows, so each one gets a real one rather than "Technology".
COMPANIES = {
    "Red Hat": "Software",
    "SAS Institute": "Analytics",
    "IBM": "Technology",
    "Cisco": "Networking",
    "Lenovo": "Hardware",
    "Epic Games": "Games",
    "Bandwidth": "Telecommunications",
    "Pendo": "Software",
    "NetApp": "Data storage",
    "Fidelity Investments": "Finance",
    "Bank of America": "Finance",
    "MetLife": "Insurance",
    "Deloitte": "Consulting",
    "Duke Energy": "Energy",
    "Honeywell": "Manufacturing",
    "Caterpillar": "Manufacturing",
    "John Deere": "Manufacturing",
    "Lockheed Martin": "Aerospace",
    "Amazon": "Technology",
    "Microsoft": "Technology",
}


@dataclass(frozen=True)
class SeedMember:
    first_name: str
    last_name: str
    major: str
    grad_year: int
    role: str = ""           # "" for a student who has not started work
    company: str = ""        # "" for no current employer
    past: tuple = ()         # (company, role title, start year, end year)
    open_to_connect: bool = True
    bio: str = ""

    @property
    def email(self):
        local = f"{self.first_name}{self.last_name}".lower()
        return f"{EMAIL_PREFIX}{local}{EMAIL_DOMAIN}"

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"


# Spread deliberately, so every directory filter has something to find:
#   - 16 majors, so a major filter narrows rather than returning everyone
#   - grad years 2018-2029, so the year filter has both alumni and students
#   - several people per company at the big employers, one or two at the rest
#   - past roles at a *different* company from the current one, which is the
#     other half of the company filter (current_company OR a past role there)
#   - a few not open to connect, and a few students with no employer at all
MEMBERS = (
    # --- Red Hat
    SeedMember("Priya", "Raman", "Computer Science", 2019, "Senior Software Engineer", "Red Hat",
               (("IBM", "Software Engineering Intern", 2018, 2018),),
               bio="Works on container tooling. Happy to talk about open source."),
    SeedMember("Daniel", "Okafor", "Computer Engineering", 2021, "Software Engineer", "Red Hat",
               bio="Kernel and storage. Ask me about the new-grad interview loop."),
    SeedMember("Hannah", "Weiss", "Computer Science", 2023,
               "Associate Software Engineer", "Red Hat",
               (("Pendo", "Engineering Intern", 2022, 2022),)),
    # --- SAS Institute
    SeedMember("Marcus", "Bell", "Statistics", 2018, "Principal Statistician", "SAS Institute",
               bio="Twelve years in model validation. I review a lot of resumes."),
    SeedMember("Sofia", "Marchetti", "Data Science", 2022, "Data Scientist", "SAS Institute",
               (("Duke Energy", "Analytics Intern", 2021, 2021),)),
    SeedMember("Tobias", "Lind", "Mathematics", 2024, "Analytics Consultant", "SAS Institute"),
    # --- IBM
    SeedMember("Grace", "Adeyemi", "Computer Science", 2020, "Site Reliability Engineer", "IBM",
               bio="On-call veteran. Ask me about SRE internships."),
    SeedMember("Nathan", "Cole", "Industrial Engineering", 2022, "Program Manager", "IBM",
               open_to_connect=False),
    # --- Cisco
    SeedMember("Ivan", "Petrov", "Electrical Engineering", 2019, "Network Engineer", "Cisco",
               (("Lenovo", "Hardware Intern", 2018, 2018),)),
    SeedMember("Leah", "Donovan", "Computer Engineering", 2023, "Security Engineer", "Cisco",
               bio="Network security. I came through the co-op programme."),
    # --- Lenovo
    SeedMember("Arjun", "Mehta", "Computer Engineering", 2020, "Firmware Engineer", "Lenovo"),
    SeedMember("Chloe", "Barnes", "Materials Science", 2024, "Design Engineer", "Lenovo"),
    # --- Epic Games
    SeedMember("Rowan", "Fitzgerald", "Computer Science", 2021, "Engine Programmer", "Epic Games",
               bio="Rendering. Portfolios matter more than grades for games."),
    SeedMember("Yuki", "Tanabe", "Computer Science", 2025, "Gameplay Engineer", "Epic Games",
               (("Microsoft", "Software Engineering Intern", 2024, 2024),)),
    # --- Bandwidth / Pendo (Raleigh startups)
    SeedMember("Elena", "Vasquez", "Computer Science", 2022, "Backend Engineer", "Bandwidth"),
    SeedMember("Caleb", "Nguyen", "Computer Science", 2023, "Product Engineer", "Pendo",
               (("Red Hat", "Software Engineering Intern", 2022, 2022),)),
    # --- NetApp
    SeedMember("Fatima", "Haddad", "Computer Engineering", 2021, "Storage Engineer", "NetApp",
               open_to_connect=False),
    # --- Finance and insurance
    SeedMember("Oliver", "Sandberg", "Economics", 2020,
               "Quantitative Analyst", "Fidelity Investments",
               bio="Moved from engineering into quant. Ask about the switch."),
    SeedMember("Amara", "Diallo", "Business Administration", 2022,
               "Technology Analyst", "Bank of America",
               (("Deloitte", "Summer Analyst", 2021, 2021),)),
    SeedMember("Peter", "Lamm", "Statistics", 2019, "Actuarial Analyst", "MetLife"),
    # --- Consulting
    SeedMember("Noor", "Siddiqui", "Industrial Engineering", 2021,
               "Technology Consultant", "Deloitte",
               bio="Client-facing work. Happy to explain what consulting is really like."),
    # --- Energy and manufacturing
    SeedMember("Walter", "Boyd", "Civil Engineering", 2018, "Project Engineer", "Duke Energy"),
    SeedMember("Simone", "Laurent", "Chemical Engineering", 2020, "Process Engineer", "Honeywell",
               (("Caterpillar", "Manufacturing Intern", 2019, 2019),)),
    SeedMember("Derek", "Oyelaran", "Mechanical Engineering", 2022,
               "Design Engineer", "Caterpillar"),
    SeedMember("Ingrid", "Halvorsen", "Mechanical Engineering", 2023,
               "Test Engineer", "John Deere"),
    # --- Aerospace
    SeedMember("Victor", "Reyes", "Aerospace Engineering", 2019,
               "Systems Engineer", "Lockheed Martin",
               bio="Clearance-required work, so I cannot say much about projects."),
    SeedMember("Bianca", "Moreau", "Aerospace Engineering", 2024,
               "Structures Engineer", "Lockheed Martin"),
    # --- Big tech
    SeedMember("Samir", "Khatri", "Computer Science", 2020, "Software Engineer", "Amazon",
               (("Bandwidth", "Software Engineering Intern", 2019, 2019),),
               bio="AWS. I have interviewed about sixty candidates."),
    SeedMember("Keiko", "Arai", "Computer Science", 2022, "Machine Learning Engineer", "Amazon"),
    SeedMember("Thomas", "Ingram", "Computer Science", 2021, "Software Engineer", "Microsoft",
               (("SAS Institute", "Software Engineering Intern", 2020, 2020),)),
    SeedMember("Zara", "Hussein", "Biomedical Engineering", 2023, "Software Engineer", "Microsoft"),
    # --- Current students: no employer, some with an internship behind them
    SeedMember("Micah", "Brennan", "Computer Science", 2026,
               past=(("Epic Games", "Engineering Intern", 2025, 2025),),
               bio="Junior. Looking for a backend internship for next summer."),
    SeedMember("Aisha", "Rahman", "Computer Engineering", 2026,
               past=(("Cisco", "Engineering Intern", 2025, 2025),)),
    SeedMember("Jonah", "Weller", "Statistics", 2027,
               bio="Sophomore. Interested in sports analytics."),
    SeedMember("Lucia", "Ferreira", "Physics", 2027, open_to_connect=False),
    SeedMember("Dmitri", "Volkov", "Electrical Engineering", 2028),
    SeedMember("Nia", "Charles", "Data Science", 2029,
               bio="First year. Still working out what I want to do."),
)

SEED_EMAILS = tuple(member.email for member in MEMBERS)


def seeded_users():
    """Only the accounts this command owns. The email prefix is the whole scope."""
    return User.objects.filter(email__startswith=EMAIL_PREFIX, email__endswith=EMAIL_DOMAIN)


def plan():
    """What is already here, so the command can say what it would change."""
    existing = set(seeded_users().values_list("email", flat=True))
    return {
        "companies to add": sum(
            1 for name in COMPANIES
            if not Company.objects.filter(name_normalized=Company.normalize_name(name)).exists()
        ),
        "people to add": sum(1 for email in SEED_EMAILS if email not in existing),
        "people to update": sum(1 for email in SEED_EMAILS if email in existing),
        "stray seeded people to remove": len(existing - set(SEED_EMAILS)),
    }


def _company(name):
    """Resolve a name the way the API does, and tag it if we just created it."""
    company, created = Company.find_or_create(name)
    if created and COMPANIES.get(name) and not company.industry_tag:
        company.industry_tag = COMPANIES[name]
        company.save(update_fields=["industry_tag"])
    return company


def _upsert(member, companies):
    user, created = User.objects.get_or_create(
        email=member.email, defaults={"username": member.email}
    )
    if created:
        user.set_unusable_password()  # fictional: there is no inbox to send a code to
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
            "current_company": companies[member.company] if member.company else None,
            "open_to_connect": member.open_to_connect,
            "account_status": Profile.AccountStatus.ACTIVE,
            "verified_via": Profile.VerifiedVia.NCSU_EMAIL,
        },
    )
    # Replaced rather than added to, so a second run does not stack duplicates.
    PastRole.objects.filter(user=user).delete()
    for company_name, role_title, start_year, end_year in member.past:
        PastRole.objects.create(
            user=user,
            company=companies[company_name],
            role_title=role_title,
            start_date=date(start_year, 5, 15),
            end_date=date(end_year, 8, 10),
        )
    return user


def seed():
    """Create or refresh the seeded directory. Returns {email: user}."""
    with transaction.atomic():
        names = set(COMPANIES) | {
            name for member in MEMBERS for name, *_ in member.past
        } | {member.company for member in MEMBERS if member.company}
        companies = {name: _company(name) for name in names}
        users = {member.email: _upsert(member, companies) for member in MEMBERS}
        # An account from an older version of this list is still ours to clean up.
        seeded_users().exclude(email__in=SEED_EMAILS).delete()
    return users


def remove():
    """Delete the seeded people. Companies stay: real members may now work there."""
    with transaction.atomic():
        deleted, _ = seeded_users().delete()
    return deleted
