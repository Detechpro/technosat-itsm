from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import OPEN_STATUSES, Ticket
from integrations.n8n import emit


class Command(BaseCommand):
    help = "Emits ticket.overdue once per overdue ticket. Run hourly from cron or an n8n schedule."

    def handle(self, *args, **options):
        now = timezone.now()
        overdue = Ticket.objects.filter(due_date__lt=now, status__in=OPEN_STATUSES, overdue_notified_at__isnull=True)
        count = 0
        for ticket in overdue:
            emit("ticket.overdue", {"ticket": ticket.number, "title": ticket.title, "due_date": ticket.due_date})
            ticket.overdue_notified_at = now
            ticket.save(update_fields=["overdue_notified_at", "updated_at"])
            count += 1
        self.stdout.write(f"Emitted {count} overdue events")
