"""Single entry point for writing audit records."""
from .models import AuditLog


def record(actor, action, target=None, **metadata):
    actor_obj = actor if getattr(actor, "is_authenticated", False) else None
    target_type = type(target).__name__.lower() if target is not None else ""
    target_id = str(target.pk) if target is not None else ""
    return AuditLog.objects.create(actor=actor_obj, action=action, target_type=target_type,
                                   target_id=target_id, metadata=metadata)
