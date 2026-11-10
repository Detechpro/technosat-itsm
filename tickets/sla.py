"""Service-level targets per priority, following ITIL practice.

Response time: how long until IT first takes action on a request.
Resolution time: how long until the request is resolved.
The clock runs in calendar time from creation. Default targets are used until an
administrator sets a policy for that priority in Django admin.
"""
from datetime import timedelta

from django.utils import timezone

# priority: (response minutes, resolution minutes)
DEFAULT_TARGETS = {
    "critical": (15, 240),      # 15 min / 4 h
    "high": (60, 480),          # 1 h / 8 h
    "medium": (240, 1440),      # 4 h / 24 h
    "low": (480, 4320),         # 8 h / 72 h
}
AT_RISK_WINDOW = timedelta(hours=2)


def targets_for(priority):
    from .models import SlaPolicy
    policy = SlaPolicy.objects.filter(priority=priority).first()
    if policy:
        return policy.response_minutes, policy.resolution_minutes
    return DEFAULT_TARGETS.get(priority, DEFAULT_TARGETS["medium"])


def due_times(priority, start=None):
    """Return (response_due, resolution_due) for a request created at `start`."""
    start = start or timezone.now()
    response, resolution = targets_for(priority)
    return start + timedelta(minutes=response), start + timedelta(minutes=resolution)
