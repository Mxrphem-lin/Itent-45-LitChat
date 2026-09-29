from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chat.models import Conversation


class Command(BaseCommand):
    help = "Assign existing ownerless conversations to the initial LitChat superuser."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as error:
            raise CommandError("The requested account does not exist.") from error
        if not user.is_superuser:
            raise CommandError("Legacy conversations can only be assigned to a superuser.")

        with transaction.atomic():
            ownerless = Conversation.objects.filter(owner__isnull=True)
            assigned_count = ownerless.update(owner=user)

        self.stdout.write(
            self.style.SUCCESS(f"Assigned {assigned_count} legacy conversation(s) to {user.username}.")
        )
