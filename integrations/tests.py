import json
import os
import time
from unittest import mock

import requests
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from tickets import services
from tickets.models import Approval, Category, Status, Ticket

from .models import InboundEvent, WebhookDelivery, WebhookEndpoint
from .n8n import MAX_ATTEMPTS, emit, sign, verify_inbound

SECRET = "outbound-secret"
INBOUND = "inbound-secret"


def signed_post(client, url, payload, event_id="evt-1", secret=INBOUND, ts=None):
    body = json.dumps(payload).encode()
    ts = str(ts or int(time.time()))
    return client.post(url, data=body, content_type="application/json", headers={
        "X-Portal-Timestamp": ts, "X-Portal-Signature": sign(secret, ts, body), "X-Event-Id": event_id})


class SigningTests(TestCase):
    def test_roundtrip_and_tamper_detection(self):
        body = b'{"a":1}'
        ts = str(int(time.time()))
        sig = sign("s", ts, body)
        self.assertTrue(verify_inbound("s", ts, body, sig))
        self.assertFalse(verify_inbound("s", ts, b'{"a":2}', sig))
        self.assertFalse(verify_inbound("wrong", ts, body, sig))

    def test_stale_timestamp_rejected(self):
        body = b"{}"
        ts = str(int(time.time()) - 3600)
        self.assertFalse(verify_inbound("s", ts, body, sign("s", ts, body)))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OutboundTests(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="Long-Passw0rd-1", email="e@x.example", role=Role.EMPLOYEE)
        self.it = User.objects.create_user("it", password="Long-Passw0rd-1", email="i@x.example", role=Role.IT_ADMIN)
        self.endpoint = WebhookEndpoint.objects.create(name="n8n", url="https://n8n.example/webhook/abc",
                                                       event_types=["ticket.created"], secret_env="TEST_OUT_SECRET")

    def test_event_delivered_with_valid_signature(self):
        with mock.patch.dict(os.environ, {"TEST_OUT_SECRET": SECRET}), \
             mock.patch("integrations.n8n.requests.post") as post:
            post.return_value = mock.Mock(status_code=200)
            with self.captureOnCommitCallbacks(execute=True):
                services.create_ticket(self.emp, title="Signed event test")
            self.assertEqual(post.call_count, 1)
            kwargs = post.call_args.kwargs
            headers = kwargs["headers"]
            self.assertTrue(verify_inbound(SECRET, headers["X-Portal-Timestamp"], kwargs["data"],
                                           headers["X-Portal-Signature"]))
            self.assertEqual(json.loads(kwargs["data"])["event"], "ticket.created")
        d = WebhookDelivery.objects.get()
        self.assertEqual(d.status, WebhookDelivery.Status.DELIVERED)

    def test_unsubscribed_events_not_queued(self):
        services.create_ticket(self.emp, title="Ticket that emits ticket.created")
        emit("laptop.assigned", {"x": 1})
        self.assertEqual(WebhookDelivery.objects.filter(event_type="laptop.assigned").count(), 0)

    def test_failed_delivery_retries_then_gives_up(self):
        delivery = WebhookDelivery.objects.create(endpoint=self.endpoint, event_type="ticket.created",
                                                  payload={"event": "ticket.created", "data": {}})
        with mock.patch("integrations.n8n.requests.post", side_effect=requests.ConnectionError("down")):
            from integrations.n8n import deliver
            for _ in range(MAX_ATTEMPTS):
                delivery.refresh_from_db()
                if delivery.status == WebhookDelivery.Status.FAILED:
                    break
                deliver(delivery.pk)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.Status.FAILED)
        self.assertEqual(delivery.attempts, MAX_ATTEMPTS)
        self.assertEqual(delivery.last_error, "ConnectionError")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class InboundTests(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="Long-Passw0rd-1", email="e@x.example", role=Role.EMPLOYEE)
        self.ticket = services.create_ticket(self.emp, title="Inbound target ticket")
        self.url = reverse("n8n_callback")

    def test_comment_from_n8n_is_applied(self):
        with mock.patch.dict(os.environ, {"N8N_INBOUND_SECRET": INBOUND}):
            resp = signed_post(self.client, self.url, {"action": "ticket.add_comment", "ticket": self.ticket.number,
                                                       "body": "Ticket enriched by workflow"}, event_id="e1")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.ticket.comments.filter(body="Ticket enriched by workflow").exists())

    def test_status_change_from_n8n(self):
        with mock.patch.dict(os.environ, {"N8N_INBOUND_SECRET": INBOUND}):
            resp = signed_post(self.client, self.url, {"action": "ticket.set_status", "ticket": self.ticket.number,
                                                       "status": "in_progress"}, event_id="e2")
        self.assertEqual(resp.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.IN_PROGRESS)

    def test_replayed_event_is_ignored(self):
        payload = {"action": "ticket.add_comment", "ticket": self.ticket.number, "body": "once"}
        with mock.patch.dict(os.environ, {"N8N_INBOUND_SECRET": INBOUND}):
            signed_post(self.client, self.url, payload, event_id="replay-1")
            resp = signed_post(self.client, self.url, payload, event_id="replay-1")
        self.assertEqual(resp.json()["status"], "duplicate_ignored")
        self.assertEqual(self.ticket.comments.filter(body="once").count(), 1)

    def test_bad_signature_rejected(self):
        with mock.patch.dict(os.environ, {"N8N_INBOUND_SECRET": INBOUND}):
            resp = signed_post(self.client, self.url, {"action": "ticket.set_status", "ticket": self.ticket.number,
                                                       "status": "closed"}, event_id="e3", secret="forged")
        self.assertEqual(resp.status_code, 401)
        self.ticket.refresh_from_db()
        self.assertNotEqual(self.ticket.status, Status.CLOSED)

    def test_unsupported_action_rejected(self):
        with mock.patch.dict(os.environ, {"N8N_INBOUND_SECRET": INBOUND}):
            resp = signed_post(self.client, self.url, {"action": "ticket.delete", "ticket": self.ticket.number},
                               event_id="e4")
        self.assertEqual(resp.status_code, 400)


class ApiTests(TestCase):
    def setUp(self):
        pw = "Long-Passw0rd-1"
        self.dept_mgr = User.objects.create_user("mgr", password=pw, role=Role.MANAGER, email="m@x.example")
        self.emp = User.objects.create_user("emp", password=pw, role=Role.EMPLOYEE, email="e@x.example",
                                            manager=self.dept_mgr)
        self.other = User.objects.create_user("other", password=pw, role=Role.EMPLOYEE, email="o@x.example")

    def login(self, username):
        resp = self.client.post(reverse("api_token"), {"username": username, "password": "Long-Passw0rd-1"},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        return resp.json()["token"]

    def auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_token_login_and_me(self):
        token = self.login("emp")
        me = self.client.get(reverse("api_me"), **self.auth(token)).json()
        self.assertEqual(me["username"], "emp")

    def test_bad_password_rejected(self):
        resp = self.client.post(reverse("api_token"), {"username": "emp", "password": "nope"},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_create_ticket_and_list_scoped(self):
        token = self.login("emp")
        resp = self.client.post("/api/v1/tickets/", {"title": "Mobile created ticket", "category": "email",
                                                     "priority": "high"}, content_type="application/json",
                                **self.auth(token))
        self.assertEqual(resp.status_code, 201)
        number = resp.json()["number"]
        other_token = self.login("other")
        listing = self.client.get("/api/v1/tickets/", **self.auth(other_token)).json()
        self.assertNotIn(number, [t["number"] for t in listing["results"]])

    def test_manager_approves_via_api(self):
        emp_token = self.login("emp")
        resp = self.client.post("/api/v1/tickets/", {"title": "Need a laptop", "category": "equipment"},
                                content_type="application/json", **self.auth(emp_token))
        self.assertEqual(resp.status_code, 201)
        mgr_token = self.login("mgr")
        approvals = self.client.get("/api/v1/approvals/", **self.auth(mgr_token)).json()["results"]
        self.assertEqual(len(approvals), 1)
        decided = self.client.post(f"/api/v1/approvals/{approvals[0]['id']}/decide/",
                                   {"decision": "approved", "comment": "ok"}, content_type="application/json",
                                   **self.auth(mgr_token))
        self.assertEqual(decided.status_code, 200)
        self.assertEqual(decided.json()["decision"], "approved")

    def test_employee_cannot_decide_others_approval(self):
        emp_token = self.login("emp")
        self.client.post("/api/v1/tickets/", {"title": "Need a monitor", "category": "equipment"},
                         content_type="application/json", **self.auth(emp_token))
        from tickets.models import Approval as A
        approval = A.objects.get()
        resp = self.client.post(f"/api/v1/approvals/{approval.pk}/decide/", {"decision": "approved"},
                                content_type="application/json", **self.auth(self.login("other")))
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_api_denied(self):
        self.assertEqual(self.client.get("/api/v1/tickets/").status_code, 401)


class MessageIntakeTests(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="Long-Passw0rd-1", email="e@x.example", role=Role.EMPLOYEE)
        self.url = reverse("n8n_callback")

    def post(self, payload, event_id):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"N8N_INBOUND_SECRET": INBOUND}):
            return signed_post(self.client, self.url, payload, event_id=event_id)

    def test_email_opens_ticket_for_known_user(self):
        resp = self.post({"action": "ticket.create_from_message", "channel": "email", "sender": "E@x.example",
                          "subject": "Cannot print to floor 3", "body": "Printer shows offline."}, "mail-1")
        self.assertEqual(resp.status_code, 201)
        ticket = Ticket.objects.get(number=resp.json()["ticket"])
        self.assertEqual(ticket.requester, self.emp)
        self.assertEqual(ticket.title, "Cannot print to floor 3")
        self.assertIn("Printer shows offline", ticket.description)

    def test_teams_message_uses_first_line_when_no_subject(self):
        resp = self.post({"action": "ticket.create_from_message", "channel": "teams", "sender": "e@x.example",
                          "body": "VPN drops every hour\nDetails follow"}, "teams-1")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Ticket.objects.get(number=resp.json()["ticket"]).title, "VPN drops every hour")

    def test_unknown_sender_is_rejected(self):
        resp = self.post({"action": "ticket.create_from_message", "channel": "email", "sender": "stranger@x.example",
                          "subject": "Hello there", "body": "Please let me in"}, "mail-2")
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_duplicate_message_not_opened_twice(self):
        payload = {"action": "ticket.create_from_message", "channel": "email", "sender": "e@x.example",
                   "subject": "Once only", "body": "x"}
        self.post(payload, "mail-dup")
        resp = self.post(payload, "mail-dup")
        self.assertEqual(resp.json()["status"], "duplicate_ignored")
        self.assertEqual(Ticket.objects.count(), 1)

    def test_bad_channel_rejected(self):
        resp = self.post({"action": "ticket.create_from_message", "channel": "sms", "sender": "e@x.example",
                          "body": "x"}, "sms-1")
        self.assertEqual(resp.status_code, 400)


class SsoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("it", password="Long-Passw0rd-1", email="it@x.example", role=Role.IT_ADMIN)
        self.emp = User.objects.create_user("emp", password="Long-Passw0rd-1", email="e@x.example", role=Role.EMPLOYEE)

    def exchange(self, email):
        from unittest import mock
        with mock.patch("accounts.sso.exchange", return_value=email):
            return self.client.post(reverse("api_sso_exchange"), {"code": "c", "redirect_uri": "http://x/cb"},
                                    content_type="application/json")

    @override_settings(PORTAL_BASE_URL="https://portal.example.com")
    def test_admin_signs_in_with_microsoft(self):
        resp = self.exchange("it@x.example")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["token"])
        self.assertEqual(resp.json()["user"]["role"], "it_admin")

    def test_employee_denied_via_sso(self):
        resp = self.exchange("e@x.example")
        self.assertEqual(resp.status_code, 403)

    def test_unknown_microsoft_account_denied(self):
        self.assertEqual(self.exchange("nobody@x.example").status_code, 403)

    @override_settings(PORTAL_BASE_URL="https://portal.example.com")
    def test_start_rejects_foreign_redirect(self):
        resp = self.client.post(reverse("api_sso_start"), {"redirect_uri": "https://evil.example/cb"},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 400)
