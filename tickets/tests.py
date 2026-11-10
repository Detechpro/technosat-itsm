from datetime import date, timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department, Invitation, Role, User
from accounts.permissions import visible_tickets
from integrations.microsoft365 import GraphClient, NotConfigured
from tickets import services
from tickets.models import Approval, Category, Status, Task, Ticket


class Base(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Finance")
        self.manager = User.objects.create_user("mgr", password="x-Passw0rd-long", role=Role.MANAGER,
                                                department=self.dept, email="mgr@example.com")
        self.employee = User.objects.create_user("emp", password="x-Passw0rd-long", role=Role.EMPLOYEE,
                                                 department=self.dept, manager=self.manager, email="emp@example.com")
        self.hr = User.objects.create_user("hr", password="x-Passw0rd-long", role=Role.HR_ADMIN, email="hr@example.com")
        self.it = User.objects.create_user("itadmin", password="x-Passw0rd-long", role=Role.IT_ADMIN, email="it@example.com")
        self.tech = User.objects.create_user("tech", password="x-Passw0rd-long", role=Role.TECHNICIAN, email="t@example.com")
        self.other = User.objects.create_user("other", password="x-Passw0rd-long", role=Role.EMPLOYEE, email="o@example.com")

    def onboarding_data(self, **overrides):
        data = dict(employee_name="Ada Lovelace", company_email="ada@contoso.example", job_title="Analyst",
                    joining_date=date.today() + timedelta(days=7), employment_type="Full-time",
                    laptop_required=True, approver=self.manager, department=self.dept)
        data.update(overrides)
        ticket_data = {"approver": data.pop("approver"), "due_date": None}
        dept = data.pop("department")
        data.pop("notes", None)
        return ticket_data, {**data, "notes": ""}, dept


class TicketNumberingTests(Base):
    def test_numbers_are_sequential_and_formatted(self):
        t1 = services.create_ticket(self.employee, title="Printer on fire")
        t2 = services.create_ticket(self.employee, title="Wi-Fi is down")
        year = timezone.now().year
        self.assertEqual(t1.number, f"IT-{year}-00001")
        self.assertEqual(t2.number, f"IT-{year}-00002")
        self.assertEqual(t1.status, Status.SUBMITTED)


class ApprovalGatingTests(Base):
    def test_onboarding_creates_no_tasks_until_approved(self):
        ticket_data, details, _ = self.onboarding_data()
        ticket = services.create_onboarding(self.hr, ticket_data=ticket_data, details=details)
        self.assertEqual(ticket.status, Status.PENDING_APPROVAL)
        self.assertEqual(ticket.tasks.count(), 0)
        approval = ticket.approvals.get()
        services.decide_approval(approval, self.manager, Approval.Decision.APPROVED, "ok")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Status.ASSIGNED)
        self.assertEqual(ticket.tasks.count(), 7)
        self.assertEqual(ticket.tasks.get(sequence=1).assignee, self.it)

    def test_only_designated_approver_can_decide(self):
        ticket = services.create_ticket(self.employee, title="Laptop please", category=Category.EQUIPMENT)
        approval = ticket.approvals.get()
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.decide_approval(approval, self.other, Approval.Decision.APPROVED)

    def test_rejection_closes_ticket_and_creates_no_tasks(self):
        ticket_data, details, _ = self.onboarding_data()
        ticket = services.create_onboarding(self.hr, ticket_data=ticket_data, details=details)
        services.decide_approval(ticket.approvals.get(), self.manager, Approval.Decision.REJECTED, "no budget")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Status.REJECTED)
        self.assertEqual(ticket.tasks.count(), 0)


class LifecycleCompletionTests(Base):
    def test_completing_all_tasks_resolves_onboarding(self):
        ticket_data, details, _ = self.onboarding_data()
        ticket = services.create_onboarding(self.hr, ticket_data=ticket_data, details=details)
        services.decide_approval(ticket.approvals.get(), self.manager, Approval.Decision.APPROVED)
        for task in ticket.tasks.all():
            task.assignee = task.assignee or self.it
            task.save()
            services.complete_task(task, task.assignee)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Status.RESOLVED)


class VisibilityTests(Base):
    def test_employee_sees_only_own_tickets(self):
        mine = services.create_ticket(self.employee, title="My issue")
        theirs = services.create_ticket(self.other, title="Other issue")
        visible = list(visible_tickets(self.employee))
        self.assertIn(mine, visible)
        self.assertNotIn(theirs, visible)

    def test_manager_sees_department_tickets(self):
        colleague_ticket = services.create_ticket(self.employee, title="Dept ticket")
        self.assertIn(colleague_ticket, visible_tickets(self.manager))

    def test_hr_sees_lifecycle_but_not_general(self):
        general = services.create_ticket(self.employee, title="General issue")
        ticket_data, details, _ = self.onboarding_data()
        lifecycle = services.create_onboarding(self.hr, ticket_data=ticket_data, details=details)
        visible = list(visible_tickets(self.hr))
        self.assertIn(lifecycle, visible)
        self.assertNotIn(general, visible)


class ViewPermissionTests(Base):
    def test_employee_cannot_open_others_ticket(self):
        theirs = services.create_ticket(self.other, title="Private issue")
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("ticket_detail", args=[theirs.pk])).status_code, 403)

    def test_employee_cannot_access_user_admin(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("user_list")).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_employee_can_submit_ticket_via_form(self):
        self.client.force_login(self.employee)
        resp = self.client.post(reverse("ticket_create"), {
            "title": "Cannot reach VPN", "description": "Error 809", "category": Category.NETWORK_SECURITY,
            "priority": "high"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Ticket.objects.filter(title="Cannot reach VPN", requester=self.employee).exists())

    def test_employee_cannot_add_internal_note(self):
        ticket = services.create_ticket(self.employee, title="Sneaky note")
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.add_comment(ticket, self.employee, "secret", is_internal=True)

    def test_technician_cannot_assign_tickets(self):
        ticket = services.create_ticket(self.employee, title="Assign me")
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.assign_ticket(ticket, self.tech, self.tech)

    def test_csv_export_respects_scope(self):
        services.create_ticket(self.other, title="Not for emp")
        self.client.force_login(self.employee)
        resp = self.client.get(reverse("ticket_export_csv"))
        self.assertNotContains(resp, "Not for emp")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class InvitationTests(Base):
    def test_invitation_flow_creates_working_account(self):
        self.client.force_login(self.it)
        resp = self.client.post(reverse("invite_create"), {
            "email": "newhire@partner-company.example", "role": Role.EMPLOYEE,
            "department": self.dept.pk, "manager": self.manager.pk})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        link = [l for l in mail.outbox[0].body.split() if "/invite/" in l][0]
        token = link.rstrip("/").split("/invite/")[1]
        self.client.logout()
        resp = self.client.post(reverse("accept_invite", args=[token]), {
            "first_name": "New", "last_name": "Hire", "employee_id": "E9",
            "password1": "Sup3r-Secret-Pass", "password2": "Sup3r-Secret-Pass"})
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(email="newhire@partner-company.example")
        self.assertEqual(user.role, Role.EMPLOYEE)
        self.assertEqual(user.manager, self.manager)
        self.assertTrue(user.check_password("Sup3r-Secret-Pass"))
        # token is single use
        self.assertEqual(self.client.get(reverse("accept_invite", args=[token])).status_code, 200)
        self.assertContains(self.client.get(reverse("accept_invite", args=[token])), "unavailable")

    def test_token_stored_only_as_hash(self):
        inv, raw = Invitation.issue(email="x@y.example", role=Role.EMPLOYEE, department=None,
                                    manager=None, invited_by=self.it)
        self.assertNotIn(raw, inv.token_hash)
        self.assertEqual(inv.token_hash, Invitation.hash_token(raw))

    def test_revoked_invitation_is_rejected(self):
        inv, raw = Invitation.issue(email="rev@y.example", role=Role.EMPLOYEE, department=None,
                                    manager=None, invited_by=self.it)
        inv.revoked_at = timezone.now()
        inv.save()
        self.assertContains(self.client.get(reverse("accept_invite", args=[raw])), "unavailable")

    def test_only_super_admin_can_invite_super_admin(self):
        self.client.force_login(self.it)
        self.client.post(reverse("invite_create"), {"email": "boss@x.example", "role": Role.SUPER_ADMIN})
        self.assertFalse(Invitation.objects.filter(email="boss@x.example").exists())


class Microsoft365Tests(Base):
    def test_dry_run_never_reports_success(self):
        client = GraphClient({"TENANT_ID": "", "CLIENT_ID": "", "CLIENT_SECRET": "", "MODE": "dry_run"})
        result = client.create_user(upn="a@b.example", display_name="A", first_name="A", last_name="B")
        self.assertEqual(result["status"], "dry_run")
        self.assertIn("DRY RUN", result["detail"])

    def test_live_mode_without_credentials_raises(self):
        client = GraphClient({"TENANT_ID": "", "CLIENT_ID": "", "CLIENT_SECRET": "", "MODE": "live"})
        with self.assertRaises(NotConfigured):
            client.disable_user(upn="a@b.example")

    def test_connection_test_reports_missing_config(self):
        result = GraphClient({"TENANT_ID": "", "CLIENT_ID": "", "CLIENT_SECRET": "", "MODE": "dry_run"}).test_connection()
        self.assertFalse(result["ok"])

    def test_m365_task_run_in_dry_run_does_not_complete_task(self):
        ticket_data, details, _ = self.onboarding_data()
        ticket = services.create_onboarding(self.hr, ticket_data=ticket_data, details=details)
        services.decide_approval(ticket.approvals.get(), self.manager, Approval.Decision.APPROVED)
        task = ticket.tasks.get(m365_action="m365_create_user")
        self.client.force_login(self.it)
        self.client.post(reverse("task_run_m365", args=[task.pk]))
        task.refresh_from_db()
        self.assertNotEqual(task.status, Task.TaskStatus.DONE)
        self.assertIn("dry_run", task.result)


class DashboardTests(Base):
    def test_dashboard_counts_come_from_database(self):
        services.create_ticket(self.employee, title="Counted one")
        self.client.force_login(self.it)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["stats"]["total"], Ticket.objects.count())
        self.assertEqual(resp.context["stats"]["open"], 1)

    def test_api_scopes_results(self):
        services.create_ticket(self.other, title="Hidden from employee")
        mine = services.create_ticket(self.employee, title="Visible to employee")
        self.client.force_login(self.employee)
        resp = self.client.get("/api/v1/tickets/")
        self.assertEqual(resp.status_code, 200)
        numbers = [t["number"] for t in resp.json()["results"]]
        self.assertEqual(numbers, [mine.number])


class BilingualTests(Base):
    def test_arabic_only_ticket_is_valid_and_displays(self):
        t = services.create_ticket(self.employee, title_ar="طابعة الطابق الثالث لا تعمل", source_language="ar")
        self.assertEqual(t.display_title, "طابعة الطابق الثالث لا تعمل")
        self.assertEqual(t.source_language, "ar")

    def test_bilingual_ticket_keeps_both_titles(self):
        t = services.create_ticket(self.employee, title="VPN drops hourly", title_ar="ينقطع VPN كل ساعة")
        self.assertEqual(t.title, "VPN drops hourly")
        self.assertEqual(t.title_ar, "ينقطع VPN كل ساعة")

    def test_empty_title_rejected(self):
        with self.assertRaises(ValidationError):
            services.create_ticket(self.employee, title="", title_ar="")

    def test_api_returns_both_languages_and_arabic_labels(self):
        self.client.force_login(self.employee)
        resp = self.client.post("/api/v1/tickets/", {"title": "Mail not syncing", "title_ar": "البريد لا يتزامن",
                                                     "description_ar": "الرسائل لا تظهر", "category": "email",
                                                     "priority": "high"}, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        body = self.client.get(f"/api/v1/tickets/{resp.json()['number']}/").json()
        self.assertEqual(body["title_ar"], "البريد لا يتزامن")
        self.assertEqual(body["priority_label_ar"], "عالية")
        self.assertEqual(body["category_label_ar"], "خدمات البريد الإلكتروني")

    def test_api_rejects_ticket_without_title(self):
        self.client.force_login(self.employee)
        resp = self.client.post("/api/v1/tickets/", {"category": "email"}, content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_user_can_set_interface_language(self):
        self.client.force_login(self.employee)
        resp = self.client.patch("/api/v1/auth/me/", {"preferred_language": "ar"}, content_type="application/json")
        self.assertEqual(resp.json()["preferred_language"], "ar")
