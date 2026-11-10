from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Role, User
from .models import Priority, SlaPolicy, Status, Ticket
from .services import add_comment, create_ticket, assign_ticket
from .sla import DEFAULT_TARGETS, due_times


class SlaTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user("req", password="x-Passw0rd-long", role=Role.EMPLOYEE)
        self.tech = User.objects.create_user("tech", password="x-Passw0rd-long", role=Role.TECHNICIAN)
        self.admin = User.objects.create_user("boss", password="x-Passw0rd-long", role=Role.IT_ADMIN)

    def test_default_targets_follow_priority(self):
        t = create_ticket(self.requester, title="Printer down", priority=Priority.CRITICAL)
        tolerance = timedelta(seconds=5)  # targets are set just before the row is saved
        self.assertAlmostEqual((t.sla_response_due - t.created_at).total_seconds(),
                               timedelta(minutes=DEFAULT_TARGETS["critical"][0]).total_seconds(), delta=tolerance.total_seconds())
        self.assertAlmostEqual((t.sla_resolution_due - t.created_at).total_seconds(),
                               timedelta(minutes=DEFAULT_TARGETS["critical"][1]).total_seconds(), delta=tolerance.total_seconds())
        self.assertEqual(t.response_status, "running")

    def test_policy_overrides_default(self):
        SlaPolicy.objects.create(priority=Priority.LOW, response_minutes=30, resolution_minutes=60)
        start = timezone.now()
        response, resolution = due_times(Priority.LOW, start)
        self.assertEqual(response, start + timedelta(minutes=30))
        self.assertEqual(resolution, start + timedelta(minutes=60))

    def test_first_staff_reply_stops_response_clock(self):
        t = create_ticket(self.requester, title="VPN issue", priority=Priority.HIGH)
        add_comment(t, self.requester, "Any update?")
        t.refresh_from_db()
        self.assertIsNone(t.first_responded_at)
        add_comment(t, self.tech, "Looking into it.")
        t.refresh_from_db()
        self.assertIsNotNone(t.first_responded_at)
        self.assertEqual(t.response_status, "met")

    def test_internal_note_does_not_count_as_response(self):
        t = create_ticket(self.requester, title="Mail rules", priority=Priority.MEDIUM)
        add_comment(t, self.tech, "Internal only", is_internal=True)
        t.refresh_from_db()
        self.assertIsNone(t.first_responded_at)

    def test_assignment_by_admin_counts_as_response(self):
        t = create_ticket(self.requester, title="Laptop slow", priority=Priority.MEDIUM)
        assign_ticket(t, self.admin, self.tech)
        t.refresh_from_db()
        self.assertIsNotNone(t.first_responded_at)

    def test_late_response_is_breached(self):
        t = create_ticket(self.requester, title="Late reply", priority=Priority.CRITICAL)
        Ticket.objects.filter(pk=t.pk).update(sla_response_due=timezone.now() - timedelta(minutes=1))
        add_comment(t, self.tech, "Finally.")
        t.refresh_from_db()
        self.assertEqual(t.response_status, "breached")

    def test_open_ticket_past_resolution_due_is_breached(self):
        t = create_ticket(self.requester, title="Overdue", priority=Priority.LOW)
        Ticket.objects.filter(pk=t.pk).update(sla_resolution_due=timezone.now() - timedelta(hours=1))
        t.refresh_from_db()
        self.assertEqual(t.resolution_status, "breached")

    def test_resolved_in_time_is_met_and_closed_stops_clock(self):
        t = create_ticket(self.requester, title="Quick fix", priority=Priority.HIGH)
        t.status = Status.RESOLVED
        t.resolved_at = timezone.now()
        t.save()
        self.assertEqual(t.resolution_status, "met")
        cancelled = create_ticket(self.requester, title="Dropped", priority=Priority.HIGH)
        cancelled.status = Status.CANCELLED
        cancelled.save()
        self.assertEqual(cancelled.resolution_status, "stopped")

    def test_dashboard_reports_sla_counts(self):
        from rest_framework.test import APIClient
        t = create_ticket(self.requester, title="Breached one", priority=Priority.CRITICAL)
        Ticket.objects.filter(pk=t.pk).update(sla_resolution_due=timezone.now() - timedelta(hours=1))
        client = APIClient()
        client.force_authenticate(self.admin)
        sla = client.get("/api/v1/dashboard/").json()["sla"]
        self.assertGreaterEqual(sla["resolution_breached"], 1)
        self.assertIn("at_risk", sla)
        self.assertIn("met_percent", sla)

    def test_dashboard_period_and_status_breakdown(self):
        from rest_framework.test import APIClient
        create_ticket(self.requester, title="Recent request", priority=Priority.MEDIUM)
        old = create_ticket(self.requester, title="Old request", priority=Priority.MEDIUM)
        Ticket.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=45))
        client = APIClient()
        client.force_authenticate(self.admin)
        d7 = client.get("/api/v1/dashboard/?days=7").json()
        d90 = client.get("/api/v1/dashboard/?days=90").json()
        self.assertEqual(d7["total"], 1)
        self.assertEqual(d90["total"], 2)
        self.assertEqual(d7["by_status"][0]["status"], Status.SUBMITTED)
        self.assertIsNone(d7["avg_resolution_hours"])
