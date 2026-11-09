import json
import os

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import HttpResponseBadRequest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from accounts.models import Role
from tickets import services
from tickets.models import Status, Ticket

from .models import InboundEvent
from .n8n import verify_inbound

User = get_user_model()


def _actor():
    user, _ = User.objects.get_or_create(
        username=settings.N8N_ACTOR_USERNAME,
        defaults={"role": Role.IT_ADMIN, "is_active": True, "first_name": "n8n", "last_name": "Service",
                  "email": "", "password": "!"},
    )
    return user


@csrf_exempt
@require_POST
def n8n_callback(request):
    """Signed inbound actions from n8n.

    Headers: X-Portal-Timestamp (unix seconds), X-Portal-Signature (sha256=HMAC of "<ts>.<raw body>"),
    X-Event-Id (unique per n8n execution, used for replay protection).
    Body: {"action": "ticket.add_comment" | "ticket.set_status", "ticket": "IT-...", ...}
    """
    secret = os.environ.get(settings.N8N_INBOUND_SECRET_ENV, "")
    if not secret:
        return JsonResponse({"error": "Inbound n8n integration is not configured."}, status=503)
    if not verify_inbound(secret, request.headers.get("X-Portal-Timestamp"), request.body,
                          request.headers.get("X-Portal-Signature")):
        return JsonResponse({"error": "Invalid or expired signature."}, status=401)
    event_id = request.headers.get("X-Event-Id", "")
    if not event_id:
        return JsonResponse({"error": "X-Event-Id header is required."}, status=400)
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    if InboundEvent.objects.filter(event_id=event_id).exists():
        return JsonResponse({"status": "duplicate_ignored"})

    action = payload.get("action", "")
    if action == "ticket.create_from_message":
        return _create_from_message(payload, event_id)
    ticket = Ticket.objects.filter(number=payload.get("ticket", "")).first()
    if ticket is None:
        return JsonResponse({"error": "Unknown ticket."}, status=404)
    actor = _actor()
    try:
        if action == "ticket.add_comment":
            services.add_comment(ticket, actor, str(payload.get("body", ""))[:5000],
                                 is_internal=bool(payload.get("internal", False)))
        elif action == "ticket.set_status":
            status = payload.get("status", "")
            if status not in Status.values:
                return JsonResponse({"error": "Unknown status."}, status=400)
            services.change_status(ticket, actor, status)
        else:
            return JsonResponse({"error": f"Unsupported action {action!r}."}, status=400)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=422)
    try:
        InboundEvent.objects.create(event_id=event_id, action=action, result="applied")
    except IntegrityError:
        pass
    return JsonResponse({"status": "applied", "ticket": ticket.number})


def _create_from_message(payload, event_id):
    """Opens a ticket from an email or Teams message. Only registered, active users may open tickets this way;
    anyone else is rejected so the workflow can reply that they need an invitation."""
    from accounts.models import User as U
    channel = payload.get("channel", "")
    if channel not in ("email", "teams"):
        return JsonResponse({"error": "channel must be 'email' or 'teams'."}, status=400)
    sender = str(payload.get("sender", "")).strip().lower()
    requester = U.objects.filter(email__iexact=sender, is_active=True).first() if sender else None
    if requester is None:
        try:
            InboundEvent.objects.create(event_id=event_id, action="ticket.create_from_message", result="unknown_sender")
        except IntegrityError:
            pass
        return JsonResponse({"status": "rejected", "reason": "unknown_sender"}, status=422)
    subject = str(payload.get("subject", "") or "").strip()
    body = str(payload.get("body", "") or "").strip()
    first_line = body.splitlines()[0] if body else ""
    title = (subject or first_line or f"Request from {channel}")[:200]
    if len(title) < 5:
        title = (f"{channel.title()} request from {requester.display_name}")[:200]
    description = f"Opened from {channel} by {requester.display_name}.\n\n{body}"[:5000]
    try:
        ticket = services.create_ticket(requester, title=title, description=description, category="general")
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=422)
    try:
        InboundEvent.objects.create(event_id=event_id, action="ticket.create_from_message", result=ticket.number)
    except IntegrityError:
        pass
    return JsonResponse({"status": "created", "ticket": ticket.number}, status=201)
