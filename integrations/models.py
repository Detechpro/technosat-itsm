import uuid

from django.db import models

from accounts.models import TimestampedModel


class WebhookEndpoint(TimestampedModel):
    """An n8n webhook URL. The signing secret is read from the environment variable named in secret_env,
    so the database never holds the secret itself."""
    name = models.CharField(max_length=120)
    url = models.URLField(max_length=500)
    event_types = models.JSONField(default=list, help_text='Event names, or ["*"] for all events.')
    secret_env = models.CharField(max_length=80, default="N8N_WEBHOOK_SECRET")
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def matches(self, event_type):
        return self.enabled and ("*" in self.event_types or event_type in self.event_types)


class WebhookDelivery(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed (retries exhausted)"

    event_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries")
    event_type = models.CharField(max_length=60, db_index=True)
    payload = models.JSONField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class InboundEvent(models.Model):
    """Records every verified inbound n8n callback so replays are ignored."""
    event_id = models.CharField(max_length=80, unique=True)
    action = models.CharField(max_length=60)
    received_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=300, blank=True)
