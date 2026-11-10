import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db import models
from django.dispatch import receiver
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Department(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Administrator"
    IT_ADMIN = "it_admin", "IT Administrator"
    TECHNICIAN = "technician", "IT Technician"
    HR_ADMIN = "hr_admin", "HR Administrator"
    MANAGER = "manager", "Department Manager"
    ASSET_MANAGER = "asset_manager", "Asset Manager"
    EMPLOYEE = "employee", "Employee"


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE, db_index=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    manager = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    employee_id = models.CharField(max_length=40, blank=True)
    preferred_language = models.CharField(max_length=2, choices=[("en", "English"), ("ar", "العربية")], default="en")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_global_admin(self):
        return self.is_superuser or self.role in (Role.SUPER_ADMIN, Role.IT_ADMIN)

    @property
    def display_name(self):
        return self.get_full_name() or self.username


def _hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class Invitation(TimestampedModel):
    """Invitation links are stored as SHA-256 hashes; the raw token is only emailed."""
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def status(self):
        if self.accepted_at:
            return "accepted"
        if self.revoked_at:
            return "revoked"
        if self.expires_at <= timezone.now():
            return "expired"
        return "pending"

    @staticmethod
    def hash_token(raw):
        return _hash_token(raw)

    @classmethod
    def issue(cls, *, email, role, department, manager, invited_by, days=7):
        raw = secrets.token_urlsafe(32)
        inv = cls.objects.create(
            email=email, role=role, department=department, manager=manager, invited_by=invited_by,
            token_hash=_hash_token(raw), expires_at=timezone.now() + timedelta(days=days),
        )
        return inv, raw

    def rotate(self, days=7):
        """Issue a new token and expiry (used for resend); clears any revocation."""
        raw = secrets.token_urlsafe(32)
        self.token_hash = _hash_token(raw)
        self.expires_at = timezone.now() + timedelta(days=days)
        self.revoked_at = None
        self.save(update_fields=["token_hash", "expires_at", "revoked_at", "updated_at"])
        return raw


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=60, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"


def _ip(request):
    return request.META.get("REMOTE_ADDR") if request is not None else None


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    AuditLog.objects.create(actor=user, action="auth.login", target_type="user",
                            target_id=str(user.pk), metadata={"ip": _ip(request)})


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request=None, **kwargs):
    AuditLog.objects.create(action="auth.login_failed", metadata={
        "username": credentials.get("username", ""), "ip": _ip(request)})


class LoginCode(TimestampedModel):
    """One-time sign-in code. Only a keyed hash is stored, never the code itself."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_codes")
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]
