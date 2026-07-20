"""Provisions (or resets the password of) a staff account for the audit
report. No self-service signup by design — run manually by an operator
with shell access:

    python manage.py create_staff_user <username>
"""

import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from portal.models import StaffUser


class Command(BaseCommand):
    help = "Create or reset the password for a staff audit-report account."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username:
            raise CommandError("username is required")

        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            raise CommandError("Passwords did not match.")
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")

        user, created = StaffUser.objects.update_or_create(
            username=username,
            defaults={"password_hash": make_password(password), "is_active": True},
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} staff user '{username}'."))
