import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import LoginCode, User, Role


class OtpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="ali", email="ali@example.com", password="x-unused-1",
                                             role=Role.EMPLOYEE, first_name="Ali")
        self.request_url = reverse("api_otp_request")
        self.verify_url = reverse("api_otp_verify")

    def _request(self, email):
        return self.client.post(self.request_url, {"email": email}, content_type="application/json")

    def _code_from_mail(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def test_unknown_email_gets_same_answer_and_no_code(self):
        res = self._request("nobody@example.com")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True})
        self.assertEqual(LoginCode.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_known_email_gets_code_by_mail_and_only_a_hash_is_stored(self):
        self.assertEqual(self._request("ali@example.com").json(), {"ok": True})
        self.assertEqual(len(mail.outbox), 1)
        lc = LoginCode.objects.get(user=self.user)
        self.assertNotIn(self._code_from_mail(), lc.code_hash)
        self.assertEqual(len(lc.code_hash), 64)

    def test_correct_code_returns_token_and_cannot_be_reused(self):
        self._request("ali@example.com")
        code = self._code_from_mail()
        res = self.client.post(self.verify_url, {"email": "ali@example.com", "code": code}, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json())
        again = self.client.post(self.verify_url, {"email": "ali@example.com", "code": code}, content_type="application/json")
        self.assertEqual(again.status_code, 401)

    def test_wrong_code_five_times_locks_the_code(self):
        self._request("ali@example.com")
        code = self._code_from_mail()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.client.post(self.verify_url, {"email": "ali@example.com", "code": wrong}, content_type="application/json")
        res = self.client.post(self.verify_url, {"email": "ali@example.com", "code": code}, content_type="application/json")
        self.assertEqual(res.status_code, 401)

    def test_expired_code_is_rejected(self):
        self._request("ali@example.com")
        code = self._code_from_mail()
        LoginCode.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(seconds=1))
        res = self.client.post(self.verify_url, {"email": "ali@example.com", "code": code}, content_type="application/json")
        self.assertEqual(res.status_code, 401)

    def test_resend_cooldown_prevents_a_second_code(self):
        self._request("ali@example.com")
        self._request("ali@example.com")
        self.assertEqual(LoginCode.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_user_gets_nothing(self):
        self.user.is_active = False
        self.user.save()
        self._request("ali@example.com")
        self.assertEqual(LoginCode.objects.count(), 0)

    def test_malformed_code_is_rejected(self):
        self._request("ali@example.com")
        res = self.client.post(self.verify_url, {"email": "ali@example.com", "code": "12ab"}, content_type="application/json")
        self.assertEqual(res.status_code, 401)
