"""n8n integration.

Outbound: domain events are stored as WebhookDelivery rows (after the DB transaction commits), then POSTed
to each subscribed n8n webhook with an HMAC-SHA256 signature. Failed sends are retried by the
`retry_webhooks` management command (run it from cron or an n8n schedule). The portal works without n8n.

Inbound: n8n calls /api/v1/integrations/n8n/callback/ with a signed body to perform ticket actions.
"""
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import WebhookDelivery, WebhookEndpoint

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 6
TIMESTAMP_TOLERANCE = 300  # seconds


def _secret(env_name):
    return os.environ.get(env_name, "")


def sign(secret, timestamp, body: bytes):
    return "sha256=" + hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def verify_inbound(secret, timestamp, body: bytes, signature):
    """Returns True only for a fresh, correctly signed request."""
    if not secret or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > TIMESTAMP_TOLERANCE:
        return False
    return hmac.compare_digest(sign(secret, timestamp, body), signature)


def emit(event_type, payload):
    """Queue an event for every subscribed endpoint. Called from the workflow services."""
    endpoints = [e for e in WebhookEndpoint.objects.filter(enabled=True) if e.matches(event_type)]
    if not endpoints:
        return
    body = {"event": event_type, "occurred_at": timezone.now().isoformat(), "data": payload}
    rows = [WebhookDelivery.objects.create(endpoint=e, event_type=event_type, payload=body,
                                           event_id=uuid.uuid4(), next_attempt_at=timezone.now())
            for e in endpoints]
    ids = [r.pk for r in rows]
    transaction.on_commit(lambda: [deliver(pk) for pk in ids])


def deliver(delivery_pk):
    """Attempts one delivery. Updates status, attempts and the error text. Never raises."""
    try:
        d = WebhookDelivery.objects.select_related("endpoint").get(pk=delivery_pk)
    except WebhookDelivery.DoesNotExist:
        return
    if d.status != WebhookDelivery.Status.PENDING:
        return
    body = json.dumps({**d.payload, "event_id": str(d.event_id)}, separators=(",", ":"), default=str).encode()
    ts = str(int(time.time()))
    secret = _secret(d.endpoint.secret_env)
    headers = {
        "Content-Type": "application/json",
        "X-Portal-Event-Id": str(d.event_id),
        "X-Portal-Event": d.event_type,
        "X-Portal-Timestamp": ts,
        "X-Portal-Signature": sign(secret, ts, body) if secret else "",
    }
    d.attempts += 1
    try:
        resp = requests.post(d.endpoint.url, data=body, headers=headers, timeout=10)
        d.response_code = resp.status_code
        ok = 200 <= resp.status_code < 300
        d.last_error = "" if ok else f"HTTP {resp.status_code}"
    except requests.RequestException as exc:
        ok = False
        d.response_code = None
        d.last_error = exc.__class__.__name__[:300]
    if ok:
        d.status = WebhookDelivery.Status.DELIVERED
        d.delivered_at = timezone.now()
        d.next_attempt_at = None
    elif d.attempts >= MAX_ATTEMPTS:
        d.status = WebhookDelivery.Status.FAILED
        d.next_attempt_at = None
    else:
        d.next_attempt_at = timezone.now() + timedelta(minutes=2 ** d.attempts)
    d.save()


def retry_pending():
    due = WebhookDelivery.objects.filter(status=WebhookDelivery.Status.PENDING, next_attempt_at__lte=timezone.now())
    count = 0
    for pk in due.values_list("pk", flat=True)[:200]:
        deliver(pk)
        count += 1
    return count
