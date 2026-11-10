import csv
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.audit import record
from accounts.models import AuditLog, Department, Role, User
from accounts.permissions import (IT_STAFF_ROLES, can_assign_tickets, can_change_status, can_manage_lifecycle,
                                  can_view_ticket, is_it_staff, require_roles, visible_tickets)
from integrations.microsoft365 import GraphClient, GraphError, NotConfigured, run_action

from . import services
from .forms import AssetForm, AssignAssetForm, AttachmentForm, CommentForm, OffboardingForm, OnboardingForm, TicketForm
from .models import (OPEN_STATUSES, Approval, Asset, Category, OffboardingRequest, OnboardingRequest, Priority,
                     Status, Task, Ticket, TicketAttachment, TicketComment)

ASSET_ROLES = (Role.SUPER_ADMIN, Role.IT_ADMIN, Role.ASSET_MANAGER)
LIFECYCLE_CATEGORIES = [Category.ONBOARDING, Category.OFFBOARDING]

CATALOG = [
    ("Employee Onboarding", Category.ONBOARDING, ["New employee onboarding", "Microsoft 365 account creation",
                                                   "Laptop allocation", "Teams and SharePoint access"]),
    ("Employee Offboarding", Category.OFFBOARDING, ["Employee termination", "Laptop recovery",
                                                     "Mailbox retention", "Access revocation"]),
    ("Email Services", Category.EMAIL, ["New email account", "Password reset", "Email migration",
                                         "Shared mailbox creation", "Distribution list creation", "Email access issue"]),
    ("IT Equipment", Category.EQUIPMENT, ["New laptop request", "Laptop replacement", "Monitor request",
                                           "Keyboard and mouse", "Equipment repair", "Equipment return"]),
    ("IT Support", Category.SUPPORT, ["Computer troubleshooting", "Software installation", "Printer issue",
                                       "Network issue", "Remote support", "General IT assistance"]),
    ("Network and Security", Category.NETWORK_SECURITY, ["VPN access", "Wi-Fi access", "MFA configuration",
                                                          "User permissions", "Security incident"]),
    ("SMTP Services", Category.SMTP, ["SMTP account creation", "SMTP credentials", "SMTP troubleshooting",
                                       "Email delivery issue"]),
]


def _lifecycle(ticket):
    try:
        return ticket.onboarding
    except ObjectDoesNotExist:
        pass
    try:
        return ticket.offboarding
    except ObjectDoesNotExist:
        return None


def _staff_assignees():
    return User.objects.filter(is_active=True, role__in=IT_STAFF_ROLES).order_by("username")


# ---------- Dashboard ----------
@require_roles(*Role.values)
def dashboard(request):
    user = request.user
    days = request.GET.get("days", "30")
    dept_id = request.GET.get("department", "")
    base = visible_tickets(user)
    if days.isdigit() and int(days) > 0:
        base = base.filter(created_at__gte=timezone.now() - timedelta(days=int(days)))
    if dept_id.isdigit():
        base = base.filter(department_id=int(dept_id))
    now = timezone.now()
    open_qs = base.filter(status__in=OPEN_STATUSES)
    stats = {
        "total": base.count(),
        "open": open_qs.count(),
        "in_progress": base.filter(status=Status.IN_PROGRESS).count(),
        "pending_approvals": Approval.objects.filter(decision=Approval.Decision.PENDING, ticket__in=base).count()
        if not user.is_global_admin else Approval.objects.filter(decision=Approval.Decision.PENDING).count(),
        "overdue": base.filter(due_date__lt=now, status__in=OPEN_STATUSES).count(),
        "resolved": base.filter(status=Status.RESOLVED).count(),
    }
    staff_view = user.is_global_admin or user.role in (Role.HR_ADMIN, Role.MANAGER)
    if staff_view:
        stats["employees"] = User.objects.filter(is_active=True).count()
        stats["active_onboarding"] = OnboardingRequest.objects.filter(ticket__status__in=OPEN_STATUSES).count()
        stats["active_offboarding"] = OffboardingRequest.objects.filter(ticket__status__in=OPEN_STATUSES).count()
    if user.is_global_admin or user.role == Role.ASSET_MANAGER:
        stats["available_laptops"] = Asset.objects.filter(category=Asset.AssetCategory.LAPTOP,
                                                          status=Asset.AssetStatus.AVAILABLE).count()
        stats["assigned_equipment"] = Asset.objects.filter(status=Asset.AssetStatus.ASSIGNED).count()

    def breakdown(field):
        return list(base.values(field).annotate(n=Count("id")).order_by("-n"))

    by_department = list(base.values("department__name").annotate(n=Count("id")).order_by("-n"))
    workload = list(open_qs.filter(assignee__isnull=False).values("assignee__username")
                    .annotate(n=Count("id")).order_by("-n")[:10])
    overdue_tasks = Task.objects.filter(ticket__in=base, due_date__lt=now).exclude(status=Task.TaskStatus.DONE) \
        .select_related("ticket")[:8]
    pending = Approval.objects.filter(decision=Approval.Decision.PENDING).select_related("ticket") \
        if user.is_global_admin else Approval.objects.filter(decision=Approval.Decision.PENDING, approver=user) \
        .select_related("ticket")
    upcoming = OnboardingRequest.objects.filter(joining_date__gte=timezone.localdate(),
                                                ticket__status__in=OPEN_STATUSES).select_related("ticket")[:6]
    ticket_ids = list(base.values_list("pk", flat=True)[:500])
    activity = AuditLog.objects.filter(target_type="ticket", target_id__in=[str(i) for i in ticket_ids]) \
        .select_related("actor")[:10] if is_it_staff(user) else []
    return render(request, "dashboard.html", {
        "stats": stats, "staff_view": staff_view,
        "by_category": breakdown("category"), "by_priority": breakdown("priority"),
        "by_status": breakdown("status"), "by_department": by_department,
        "workload": workload, "overdue_tasks": overdue_tasks, "pending": pending[:8],
        "upcoming": upcoming, "activity": activity,
        "departments": Department.objects.all(), "days": days, "dept_id": dept_id,
        "category_labels": dict(Category.choices), "priority_labels": dict(Priority.choices),
        "status_labels": dict(Status.choices),
    })


# ---------- Tickets ----------
@require_roles(*Role.values)
def ticket_list(request):
    qs = visible_tickets(request.user).select_related("requester", "assignee")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q))
    for field in ("status", "priority", "category"):
        value = request.GET.get(field, "")
        if value:
            qs = qs.filter(**{field: value})
    if request.GET.get("mine"):
        qs = qs.filter(requester=request.user)
    sort = request.GET.get("sort", "-created_at")
    if sort.lstrip("-") in ("created_at", "due_date", "priority", "status", "number"):
        qs = qs.order_by(sort)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "tickets/ticket_list.html", {
        "page": page, "q": q, "sort": sort, "status_choices": Status.choices,
        "priority_choices": Priority.choices, "category_choices": Category.choices,
        "filters": {k: request.GET.get(k, "") for k in ("status", "priority", "category", "mine")},
    })


@require_roles(*Role.values)
def ticket_create(request):
    initial = {}
    if request.GET.get("category") in dict(Category.choices):
        initial["category"] = request.GET["category"]
    if request.GET.get("title"):
        initial["title"] = request.GET["title"]
    form = TicketForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            ticket = services.create_ticket(
                request.user, title=form.cleaned_data["title"], title_ar=form.cleaned_data["title_ar"],
                description=form.cleaned_data["description"], description_ar=form.cleaned_data["description_ar"],
                source_language=form.cleaned_data["source_language"], category=form.cleaned_data["category"],
                priority=form.cleaned_data["priority"], due_date=form.cleaned_data["due_date"])
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            messages.success(request, f"Ticket {ticket.number} created.")
            return redirect("ticket_detail", pk=ticket.pk)
    return render(request, "form_page.html", {"form": form, "title": "New request",
                                              "submit_label": "Submit request", "back_url": reverse("ticket_list")})


@require_roles(*Role.values)
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related("requester", "assignee", "department", "approver"), pk=pk)
    if not can_view_ticket(request.user, ticket):
        raise PermissionDenied
    user = request.user
    staff = is_it_staff(user)
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "comment":
                form = CommentForm(request.POST)
                if form.is_valid():
                    services.add_comment(ticket, user, form.cleaned_data["body"],
                                         is_internal=form.cleaned_data["is_internal"] and staff)
                    messages.success(request, "Comment added.")
                else:
                    messages.error(request, "Please enter a comment (up to 5000 characters).")
            elif action == "status":
                services.change_status(ticket, user, request.POST.get("status", ""))
                messages.success(request, "Status updated.")
            elif action == "assign":
                if not can_assign_tickets(user):
                    raise PermissionDenied
                assignee = User.objects.filter(pk=request.POST.get("assignee") or None).first()
                services.assign_ticket(ticket, user, assignee)
                messages.success(request, "Ticket assigned." if assignee else "Ticket unassigned.")
            elif action == "priority":
                if not can_change_status(user, ticket):
                    raise PermissionDenied
                if request.POST.get("priority") in dict(Priority.choices):
                    old = ticket.priority
                    ticket.priority = request.POST["priority"]
                    ticket.save(update_fields=["priority", "updated_at"])
                    record(user, "ticket.priority_changed", ticket, old=old, new=ticket.priority)
                    messages.success(request, "Priority updated.")
            elif action == "reopen":
                services.reopen_ticket(ticket, user)
                messages.success(request, "Ticket reopened.")
            elif action == "upload":
                form = AttachmentForm(request.POST, request.FILES)
                if form.is_valid():
                    f = form.cleaned_data["file"]
                    TicketAttachment.objects.create(ticket=ticket, uploaded_by=user, file=f, original_name=f.name[:255])
                    record(user, "ticket.attachment_added", ticket, filename=f.name[:255])
                    messages.success(request, "File uploaded.")
                else:
                    messages.error(request, form.errors.get("file", ["Upload failed."])[0])
        except PermissionDenied:
            messages.error(request, "You do not have permission to do that.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect("ticket_detail", pk=ticket.pk)

    comments = ticket.comments.select_related("author")
    if not staff:
        comments = comments.filter(is_internal=False)
    activity = AuditLog.objects.filter(target_type="ticket", target_id=str(ticket.pk)).select_related("actor") \
        if staff else []
    return render(request, "tickets/ticket_detail.html", {
        "ticket": ticket, "comments": comments, "comment_form": CommentForm(),
        "attachments": ticket.attachments.all(), "upload_form": AttachmentForm(),
        "tasks": ticket.tasks.select_related("assignee"), "approvals": ticket.approvals.select_related("approver"),
        "lifecycle": _lifecycle(ticket), "activity": activity, "staff": staff,
        "can_status": can_change_status(user, ticket), "can_assign": can_assign_tickets(user),
        "staff_users": _staff_assignees() if can_assign_tickets(user) else [],
        "status_choices": [c for c in Status.choices if c[0] not in ("pending_approval", "approved", "rejected")],
        "priority_choices": Priority.choices, "is_requester": ticket.requester_id == user.pk,
        "can_run_m365": user.is_global_admin,
    })


@require_roles(*Role.values)
def attachment_download(request, pk):
    att = get_object_or_404(TicketAttachment.objects.select_related("ticket"), pk=pk)
    if not can_view_ticket(request.user, att.ticket):
        raise PermissionDenied
    response = HttpResponse(att.file.open("rb").read(), content_type="application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{att.original_name}"'
    return response


@require_roles(*Role.values)
def ticket_export_csv(request):
    rows = visible_tickets(request.user).select_related("requester", "assignee", "department")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="tickets.csv"'
    writer = csv.writer(response)
    writer.writerow(["Number", "Title", "Category", "Priority", "Status", "Requester", "Department",
                     "Assignee", "Created", "Due", "Resolved"])
    for t in rows:
        writer.writerow([t.number, t.title, t.get_category_display(), t.get_priority_display(),
                         t.get_status_display(), t.requester.display_name,
                         t.department.name if t.department else "", t.assignee.display_name if t.assignee else "",
                         t.created_at.isoformat(), t.due_date.isoformat() if t.due_date else "",
                         t.resolved_at.isoformat() if t.resolved_at else ""])
    return response


@require_roles(*Role.values)
def catalog(request):
    return render(request, "tickets/catalog.html", {"catalog": CATALOG})


# ---------- Tasks ----------
@require_roles(*Role.values)
def my_tasks(request):
    tasks = Task.objects.filter(assignee=request.user).select_related("ticket").order_by("status", "due_date", "id")
    return render(request, "tickets/my_tasks.html", {"tasks": tasks})


@require_POST
@require_roles(*Role.values)
def task_update(request, pk):
    task = get_object_or_404(Task.objects.select_related("ticket"), pk=pk)
    if not can_view_ticket(request.user, task.ticket):
        raise PermissionDenied
    try:
        services.complete_task(task, request.user, done=request.POST.get("done") == "1")
        messages.success(request, "Task updated.")
    except PermissionDenied as exc:
        messages.error(request, str(exc))
    return redirect(request.POST.get("next") or "my_tasks")


@require_POST
@require_roles(Role.SUPER_ADMIN, Role.IT_ADMIN)
def task_run_m365(request, pk):
    """Runs a Microsoft 365 step. Dry-run results are recorded but never mark the task done."""
    task = get_object_or_404(Task.objects.select_related("ticket"), pk=pk)
    life = _lifecycle(task.ticket)
    if not task.m365_action or life is None:
        messages.error(request, "This task has no Microsoft 365 automation.")
        return redirect("ticket_detail", pk=task.ticket_id)
    upn = life.company_email
    first, _, last = life.employee_name.partition(" ")
    try:
        result = run_action(task.m365_action, upn=upn, display_name=life.employee_name,
                            first_name=first, last_name=last,
                            job_title=getattr(life, "job_title", ""))
    except NotConfigured as exc:
        result = {"status": "not_configured", "detail": str(exc)}
    except GraphError as exc:
        result = {"status": "failed", "detail": str(exc)}
    task.result = f"[{timezone.now():%Y-%m-%d %H:%M}] {result['status']}: {result['detail']}"
    task.save(update_fields=["result", "updated_at"])
    record(request.user, f"m365.{result['status']}", task, m365_action=task.m365_action, upn=upn)
    if result["status"] == "success":
        services.complete_task(task, request.user, done=True)
        messages.success(request, "Microsoft 365 step completed.")
    elif result["status"] == "dry_run":
        messages.info(request, "Dry run only. Nothing changed in Microsoft 365. Set M365_MODE=live to execute.")
    else:
        messages.error(request, result["detail"])
    return redirect("ticket_detail", pk=task.ticket_id)


# ---------- Approvals ----------
@require_roles(*Role.values)
def approvals(request):
    user = request.user
    base = Approval.objects.select_related("ticket", "ticket__requester", "approver")
    if user.is_global_admin:
        pending = base.filter(decision=Approval.Decision.PENDING)
    else:
        pending = base.filter(decision=Approval.Decision.PENDING, approver=user)
    history = base.exclude(decision=Approval.Decision.PENDING).filter(approver=user)[:50]
    return render(request, "tickets/approvals.html", {"pending": pending, "history": history})


@require_POST
@require_roles(*Role.values)
def approval_decide(request, pk):
    approval = get_object_or_404(Approval.objects.select_related("ticket"), pk=pk)
    decision = request.POST.get("decision")
    if decision not in (Approval.Decision.APPROVED, Approval.Decision.REJECTED):
        messages.error(request, "Choose approve or reject.")
    else:
        try:
            services.decide_approval(approval, request.user, decision, request.POST.get("comment", "")[:2000])
            messages.success(request, f"Request {decision}.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("approvals")


# ---------- Employee lifecycle ----------
@require_roles(*Role.values)
def lifecycle_list(request, kind):
    category = Category.ONBOARDING if kind == "onboarding" else Category.OFFBOARDING
    if not (can_manage_lifecycle(request.user) or request.user.role == Role.MANAGER):
        raise PermissionDenied
    qs = visible_tickets(request.user).filter(category=category).select_related("requester")
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "tickets/lifecycle_list.html", {"page": page, "kind": kind,
                                                            "title": "Onboarding" if kind == "onboarding" else "Offboarding"})


@require_roles(Role.SUPER_ADMIN, Role.IT_ADMIN, Role.HR_ADMIN)
def lifecycle_create(request, kind):
    if kind not in ("onboarding", "offboarding"):
        raise PermissionDenied
    FormClass = OnboardingForm if kind == "onboarding" else OffboardingForm
    form = FormClass(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        ticket_data = {"approver": data.pop("approver"), "due_date": None}
        dept = data.pop("department")
        notes = data.pop("notes", "")
        try:
            if kind == "onboarding":
                ticket = services.create_onboarding(request.user, ticket_data=ticket_data,
                                                    details={**data, "notes": notes})
            else:
                ticket = services.create_offboarding(request.user, ticket_data=ticket_data,
                                                     details={**data, "notes": notes})
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            if dept:
                ticket.department = dept
                ticket.save(update_fields=["department", "updated_at"])
            messages.success(request, f"{ticket.number} submitted for manager approval.")
            return redirect("ticket_detail", pk=ticket.pk)
    title = "New onboarding request" if kind == "onboarding" else "New offboarding request"
    return render(request, "form_page.html", {"form": form, "title": title, "submit_label": "Submit for approval",
                                              "back_url": reverse("lifecycle_list", args=[kind])})


# ---------- Assets ----------
@require_roles(*ASSET_ROLES, Role.TECHNICIAN, Role.HR_ADMIN, Role.MANAGER)
def asset_list(request):
    qs = Asset.objects.select_related("assigned_to", "department")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(asset_tag__icontains=q) | Q(name__icontains=q) | Q(serial_number__icontains=q))
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "tickets/asset_list.html", {
        "page": page, "q": q, "status": status, "status_choices": Asset.AssetStatus.choices,
        "can_manage": request.user.is_global_admin or request.user.role == Role.ASSET_MANAGER,
        "assignable_users": User.objects.filter(is_active=True).order_by("username")[:300],
    })


@require_roles(*ASSET_ROLES)
def asset_create(request):
    form = AssetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        asset = form.save()
        record(request.user, "asset.created", asset, tag=asset.asset_tag)
        messages.success(request, f"Asset {asset.asset_tag} added.")
        return redirect("asset_list")
    return render(request, "form_page.html", {"form": form, "title": "Add asset", "submit_label": "Save asset",
                                              "back_url": reverse("asset_list")})


@require_POST
@require_roles(*ASSET_ROLES)
def asset_assign(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    if request.POST.get("action") == "return":
        if asset.status != Asset.AssetStatus.ASSIGNED:
            messages.error(request, "This asset is not currently assigned.")
        else:
            previous = asset.assigned_to
            asset.assigned_to = None
            asset.status = Asset.AssetStatus.RETURNED
            asset.save(update_fields=["assigned_to", "status", "updated_at"])
            record(request.user, "asset.returned", asset, previous=previous.username if previous else None)
            messages.success(request, f"{asset.asset_tag} returned.")
        return redirect("asset_list")
    form = AssignAssetForm(request.POST)
    if form.is_valid():
        if asset.status in (Asset.AssetStatus.RETIRED, Asset.AssetStatus.DAMAGED, Asset.AssetStatus.MAINTENANCE):
            messages.error(request, f"Cannot assign an asset that is {asset.get_status_display().lower()}.")
        else:
            user = form.cleaned_data["user"]
            asset.assigned_to = user
            asset.department = user.department
            asset.status = Asset.AssetStatus.ASSIGNED
            asset.save(update_fields=["assigned_to", "department", "status", "updated_at"])
            record(request.user, "asset.assigned", asset, assignee=user.username)
            messages.success(request, f"{asset.asset_tag} assigned to {user.display_name}.")
    else:
        messages.error(request, "Choose a user to assign this asset to.")
    return redirect("asset_list")


# ---------- Microsoft 365 admin ----------
@require_roles(Role.SUPER_ADMIN, Role.IT_ADMIN)
def m365_status(request):
    client = GraphClient()
    result = None
    if request.method == "POST":
        result = client.test_connection()
        record(request.user, "m365.connection_test", None, ok=result["ok"])
    from django.conf import settings
    cfg = settings.MICROSOFT365
    return render(request, "tickets/m365.html", {
        "configured": client.is_configured, "mode": cfg["MODE"], "tenant_set": bool(cfg["TENANT_ID"]),
        "client_id_set": bool(cfg["CLIENT_ID"]), "secret_set": bool(cfg["CLIENT_SECRET"]),
        "license_set": bool(cfg["DEFAULT_LICENSE_SKU_ID"]), "result": result,
    })
