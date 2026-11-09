"""Workflow engine: ticket creation, approvals, task generation and status transitions.

Sensitive work (account creation, permission changes) is only created as tasks
after the required approval has been recorded.
"""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.audit import record
from accounts.models import Role, User
from accounts.permissions import can_change_status, can_assign_tickets
from integrations.n8n import emit

from .models import (APPROVAL_CATEGORIES, Approval, Category, OffboardingRequest, OnboardingRequest, Priority,
                     Status, Task, Ticket, TicketComment)

ONBOARDING_TASKS = [
    ("Create Microsoft 365 account", Role.IT_ADMIN, "m365_create_user"),
    ("Allocate Microsoft 365 license", Role.IT_ADMIN, "m365_assign_license"),
    ("Prepare laptop", Role.TECHNICIAN, ""),
    ("Install required software", Role.TECHNICIAN, ""),
    ("Configure application access", Role.TECHNICIAN, ""),
    ("Configure MFA and security", Role.IT_ADMIN, ""),
    ("Final verification", Role.IT_ADMIN, ""),
]
OFFBOARDING_TASKS = [
    ("Schedule account disablement", Role.IT_ADMIN, "m365_disable_user"),
    ("Revoke active sign-in sessions", Role.IT_ADMIN, "m365_revoke_sessions"),
    ("Revoke application and VPN access", Role.TECHNICIAN, ""),
    ("Apply mailbox retention and forwarding", Role.IT_ADMIN, ""),
    ("Recover laptop", Role.TECHNICIAN, ""),
    ("Recover accessories", Role.TECHNICIAN, ""),
    ("Remove access permissions", Role.IT_ADMIN, ""),
    ("Verify all tasks", Role.IT_ADMIN, ""),
]


def _notify(user, subject, body):
    """Email notification. Failures are logged to the audit trail rather than raised."""
    if not user or not user.email:
        return
    try:
        send_mail(f"[IT Service Portal] {subject}", body, None, [user.email], fail_silently=False)
    except Exception as exc:
        record(None, "notification.failed", user, subject=subject, error=exc.__class__.__name__)


def _ticket_payload(ticket):
    return {"ticket": ticket.number, "title": ticket.title, "category": ticket.category,
            "status": ticket.status, "priority": ticket.priority, "requester": ticket.requester.username,
            "assignee": ticket.assignee.username if ticket.assignee_id else None}


def _log(ticket, actor, action, **meta):
    record(actor, action, ticket, ticket_number=ticket.number, **meta)


def _default_assignee(role):
    return User.objects.filter(role=role, is_active=True).order_by("id").first()


@transaction.atomic
def create_ticket(requester, *, title, description="", category=Category.GENERAL,
                  priority=Priority.MEDIUM, due_date=None, approver=None):
    if category in APPROVAL_CATEGORIES:
        approver = approver or requester.manager
        if approver is None:
            raise ValidationError("This request type needs a manager approver. Set a reporting manager first.")
    ticket = Ticket.objects.create(
        title=title, description=description, category=category, priority=priority, due_date=due_date,
        requester=requester, department=requester.department, approver=approver,
        status=Status.PENDING_APPROVAL if category in APPROVAL_CATEGORIES else Status.SUBMITTED,
    )
    if category in APPROVAL_CATEGORIES:
        Approval.objects.create(ticket=ticket, approver=approver, level=1)
        _notify(approver, f"Approval required: {ticket.number}", f"{requester.display_name} submitted: {title}")
    _log(ticket, requester, "ticket.created", category=category)
    emit("ticket.created", _ticket_payload(ticket))
    if category in APPROVAL_CATEGORIES:
        emit("approval.requested", _ticket_payload(ticket))
    return ticket


@transaction.atomic
def create_onboarding(hr_user, *, ticket_data, details):
    ticket = create_ticket(hr_user, approver=ticket_data.get("approver"), category=Category.ONBOARDING,
                           title=f"Onboarding: {details['employee_name']}",
                           description=details.get("notes", ""), priority=Priority.HIGH,
                           due_date=ticket_data.get("due_date"))
    OnboardingRequest.objects.create(ticket=ticket, **{k: v for k, v in details.items() if k != "notes"})
    return ticket


@transaction.atomic
def create_offboarding(hr_user, *, ticket_data, details):
    ticket = create_ticket(hr_user, approver=ticket_data.get("approver"), category=Category.OFFBOARDING,
                           title=f"Offboarding: {details['employee_name']}",
                           description=details.get("notes", ""), priority=Priority.CRITICAL,
                           due_date=details["termination_at"])
    OffboardingRequest.objects.create(ticket=ticket, **{k: v for k, v in details.items() if k != "notes"})
    return ticket


def _generate_tasks(ticket):
    template = ONBOARDING_TASKS if ticket.category == Category.ONBOARDING else OFFBOARDING_TASKS
    for seq, (title, role, m365_action) in enumerate(template, start=1):
        Task.objects.create(ticket=ticket, title=title, assignee=_default_assignee(role),
                            sequence=seq, m365_action=m365_action, priority=ticket.priority,
                            due_date=ticket.due_date)
    if ticket.category in (Category.ONBOARDING, Category.OFFBOARDING):
        ticket.status = Status.ASSIGNED
        ticket.save(update_fields=["status", "updated_at"])


@transaction.atomic
def decide_approval(approval, actor, decision, comment=""):
    ticket = approval.ticket
    if approval.approver_id != actor.pk:
        raise PermissionDenied("Only the assigned approver can decide this request.")
    if approval.decision != Approval.Decision.PENDING:
        raise ValidationError("This approval has already been decided.")
    if ticket.status != Status.PENDING_APPROVAL:
        raise ValidationError("This ticket is not waiting for approval.")
    approval.decision = decision
    approval.comment = comment
    approval.decided_at = timezone.now()
    approval.save(update_fields=["decision", "comment", "decided_at", "updated_at"])
    _log(ticket, actor, f"approval.{decision}", comment=comment)
    emit(f"approval.{decision}", _ticket_payload(ticket))
    if decision == Approval.Decision.APPROVED:
        ticket.status = Status.APPROVED
        ticket.save(update_fields=["status", "updated_at"])
        if ticket.category in (Category.ONBOARDING, Category.OFFBOARDING):
            _generate_tasks(ticket)
        _notify(ticket.requester, f"Approved: {ticket.number}", f"{ticket.title} was approved.")
    else:
        ticket.status = Status.REJECTED
        ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status", "closed_at", "updated_at"])
        _notify(ticket.requester, f"Rejected: {ticket.number}", f"{ticket.title} was rejected. {comment}")


@transaction.atomic
def change_status(ticket, actor, new_status):
    if not can_change_status(actor, ticket):
        raise PermissionDenied("You are not allowed to change this ticket's status.")
    if new_status in (Status.PENDING_APPROVAL, Status.APPROVED, Status.REJECTED):
        raise ValidationError("Approval states are set by the approval workflow only.")
    old = ticket.status
    ticket.status = new_status
    now = timezone.now()
    if new_status == Status.RESOLVED:
        ticket.resolved_at = now
    if new_status == Status.CLOSED:
        ticket.closed_at = now
    ticket.save()
    _log(ticket, actor, "ticket.status_changed", old=old, new=new_status)
    emit("ticket.status_changed", {**_ticket_payload(ticket), "old_status": old})
    if new_status in (Status.RESOLVED, Status.CLOSED):
        _notify(ticket.requester, f"Resolved: {ticket.number}", f"{ticket.title} is now {new_status}.")
    return ticket


@transaction.atomic
def assign_ticket(ticket, actor, assignee):
    if not can_assign_tickets(actor):
        raise PermissionDenied("Only administrators can assign tickets.")
    previous = ticket.assignee
    ticket.assignee = assignee
    if ticket.status in (Status.NEW, Status.SUBMITTED, Status.APPROVED):
        ticket.status = Status.ASSIGNED
    ticket.save()
    _log(ticket, actor, "ticket.assigned", previous=getattr(previous, "username", None),
         assignee=getattr(assignee, "username", None))
    emit("ticket.assigned", {**_ticket_payload(ticket), "assignee": getattr(assignee, "username", None)})
    _notify(assignee, f"Assigned: {ticket.number}", f"You were assigned: {ticket.title}")
    return ticket


@transaction.atomic
def complete_task(task, actor, done=True):
    """Marks a task done/undone. Lifecycle tickets resolve automatically when every task is done."""
    ticket = task.ticket
    if task.assignee_id != actor.pk and not actor.is_global_admin:
        raise PermissionDenied("Only the task assignee can update this task.")
    task.status = Task.TaskStatus.DONE if done else Task.TaskStatus.IN_PROGRESS
    task.completed_at = timezone.now() if done else None
    task.save(update_fields=["status", "completed_at", "updated_at"])
    _log(ticket, actor, "task.completed" if done else "task.reopened", task=task.title)
    if done:
        emit("task.completed", {**_ticket_payload(ticket), "task": task.title})

    if ticket.category in (Category.ONBOARDING, Category.OFFBOARDING):
        all_done = not ticket.tasks.exclude(status=Task.TaskStatus.DONE).exists()
        if all_done and ticket.status != Status.RESOLVED:
            ticket.status = Status.RESOLVED
            ticket.resolved_at = timezone.now()
            ticket.save()
            _log(ticket, actor, "lifecycle.completed")
            emit("lifecycle.completed", _ticket_payload(ticket))
            _notify(ticket.requester, f"Completed: {ticket.number}", f"All IT tasks finished for {ticket.title}.")
        elif not all_done and ticket.status == Status.ASSIGNED:
            ticket.status = Status.IN_PROGRESS
            ticket.save()
    elif done and ticket.status == Status.ASSIGNED:
        ticket.status = Status.IN_PROGRESS
        ticket.save()
    return task


@transaction.atomic
def add_comment(ticket, author, body, is_internal=False):
    if is_internal and author.role not in (Role.SUPER_ADMIN, Role.IT_ADMIN, Role.TECHNICIAN, Role.ASSET_MANAGER) \
            and not author.is_superuser:
        raise PermissionDenied("Only IT staff can add internal notes.")
    comment = TicketComment.objects.create(ticket=ticket, author=author, body=body, is_internal=is_internal)
    _log(ticket, author, "ticket.commented", internal=is_internal)
    return comment


@transaction.atomic
def reopen_ticket(ticket, actor):
    if actor.pk != ticket.requester_id and not actor.is_global_admin:
        raise PermissionDenied("Only the requester can reopen this ticket.")
    if ticket.status not in (Status.RESOLVED, Status.CLOSED):
        raise ValidationError("Only resolved or closed tickets can be reopened.")
    ticket.status = Status.IN_PROGRESS if ticket.assignee_id else Status.SUBMITTED
    ticket.resolved_at = None
    ticket.closed_at = None
    ticket.save()
    _log(ticket, actor, "ticket.reopened")
    return ticket
