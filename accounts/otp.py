"""Email one-time codes for sign-in. Codes are six digits, expire after 10 minutes,
allow five wrong attempts, and can be used once."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import LoginCode, User

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5


def _hash(user_id: int, code: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def find_user(email: str):
    """Active users only. Returns None for anything else, without saying why."""
    if not email:
        return None
    return User.objects.filter(email__iexact=email, is_active=True).first()


def issue(user: User):
    """Create a new code. Returns the plain code, or None during the resend cooldown."""
    now = timezone.now()
    if LoginCode.objects.filter(user=user, created_at__gt=now - RESEND_COOLDOWN).exists():
        return None
    LoginCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)  # retire older codes
    code = f"{secrets.randbelow(1_000_000):06d}"
    LoginCode.objects.create(user=user, code_hash=_hash(user.pk, code), expires_at=now + CODE_TTL)
    return code


def send(user: User, code: str) -> None:
    send_mail(
        subject="Your IT Service Portal sign-in code",
        message=(
            f"Your sign-in code is {code}.\n\n"
            "It expires in 10 minutes. If you did not request it, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def verify(user: User, code: str) -> bool:
    now = timezone.now()
    latest = LoginCode.objects.filter(user=user, used_at__isnull=True).first()  # newest unused code
    if latest is None or latest.expires_at <= now or latest.attempts >= MAX_ATTEMPTS:
        return False
    if hmac.compare_digest(latest.code_hash, _hash(user.pk, code)):
        latest.used_at = now
        latest.save(update_fields=["used_at", "updated_at"])
        return True
    latest.attempts += 1
    latest.save(update_fields=["attempts", "updated_at"])
    return False
