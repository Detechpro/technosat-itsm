from django.core.management.base import BaseCommand

from integrations.n8n import retry_pending


class Command(BaseCommand):
    help = "Retry pending n8n webhook deliveries whose backoff time has passed. Run every minute from cron."

    def handle(self, *args, **options):
        self.stdout.write(f"Attempted {retry_pending()} deliveries")
