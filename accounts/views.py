from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .audit import record
from .forms import AcceptInviteForm, InviteForm
from .models import AuditLog, Invitation, Role, User
from .permissions import can_invite, can_manage_users, require_roles


def _send_invitation(request, invitation, raw_token):
    link = request.build_absolute_uri(reverse("accept_invite", args=[raw_token]))
    body = (f"You have been invited to the IT Service Portal as {invitation.get_role_display()}.\n\n"
            f"Create your account here (link expires {invitation.expires_at:%Y-%m-%d %H:%M} UTC):\n{link}\n\n"
            "If you were not expecting this invitation, ignore this email.")
    try:
        send_mail("You're invited to the IT Service Portal", body, None, [invitation.email], fail_silently=False)
        return True
    except Exception as exc:  # SMTP failures must not crash the admin workflow
        messages.error(request, f"Invitation saved, but the email could not be sent ({exc.__class__.__name__}). "
                                "Check SMTP settings, then use Resend.")
        return False


@require_roles(Role.SUPER_ADMIN, Role.IT_ADMIN)
def user_list(request):
    users = User.objects.select_related("department", "manager").order_by("username")
    invitations = Invitation.objects.select_related("department").order_by("-created_at")[:100]
    return render(request, "accounts/users.html", {"users": users, "invitations": invitations,
                                                   "can_manage": can_manage_users(request.user)})


@require_roles(Role.SUPER_ADMIN, Role.IT_ADMIN)
def invite_create(request):
    form = InviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower()
        role = form.cleaned_data["role"]
        if role == Role.SUPER_ADMIN and not can_manage_users(request.user):
            form.add_error("role", "Only a Super Administrator can invite another Super Administrator.")
        elif User.objects.filter(email__iexact=email).exists():
            form.add_error("email", "A user with this email already exists.")
        elif Invitation.objects.filter(email__iexact=email, accepted_at__isnull=True, revoked_at__isnull=True,
                                       expires_at__gt=timezone.now()).exists():
            form.add_error("email", "A pending invitation already exists. Resend or revoke it instead.")
        else:
            inv, raw = Invitation.issue(
                email=email, role=role, department=form.cleaned_data["department"],
                manager=form.cleaned_data["manager"], invited_by=request.user)
            record(request.user, "invitation.created", inv, email=email, role=role)
            if _send_invitation(request, inv, raw):
                messages.success(request, f"Invitation sent to {email}.")
            return redirect("user_list")
    return render(request, "form_page.html", {
        "form": form, "title": "Invite user", "submit_label": "Send invitation",
        "back_url": reverse("user_list"),
        "intro": "Invitations expire after 7 days. Any email domain can be invited.",
    })


@require_POST
@require_roles(Role.SUPER_ADMIN, Role.IT_ADMIN)
def invitation_resend(request, pk):
    inv = get_object_or_404(Invitation, pk=pk)
    if inv.status == "accepted":
        messages.error(request, "This invitation was already accepted.")
    else:
        raw = inv.rotate()
        record(request.user, "invitation.resent", inv, email=inv.email)
        if _send_invitation(request, inv, raw):
            messages.success(request, f"Invitation re-sent to {inv.email}.")
    return redirect("user_list")


@require_POST
@require_roles(Role.SUPER_ADMIN, Role.IT_ADMIN)
def invitation_revoke(request, pk):
    inv = get_object_or_404(Invitation, pk=pk)
    if inv.status in ("pending", "expired"):
        inv.revoked_at = timezone.now()
        inv.save(update_fields=["revoked_at", "updated_at"])
        record(request.user, "invitation.revoked", inv, email=inv.email)
        messages.success(request, f"Invitation for {inv.email} revoked.")
    return redirect("user_list")


@require_POST
@require_roles(Role.SUPER_ADMIN)
def user_toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active", "updated_at"])
        action = "user.activated" if target.is_active else "user.deactivated"
        record(request.user, action, target, username=target.username)
        messages.success(request, f"{target.display_name} is now {'active' if target.is_active else 'inactive'}.")
    return redirect("user_list")


def accept_invite(request, token):
    inv = Invitation.objects.filter(token_hash=Invitation.hash_token(token)).select_related("department", "manager").first()
    if inv is None or inv.status != "pending" or User.objects.filter(email__iexact=inv.email).exists():
        return render(request, "accounts/invite_invalid.html", {"invitation": inv})
    form = AcceptInviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            inv = Invitation.objects.select_for_update().get(pk=inv.pk)
            if inv.status != "pending":
                messages.error(request, "This invitation is no longer valid.")
                return redirect("login")
            user = User.objects.create_user(
                username=inv.email.lower(), email=inv.email,
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data["first_name"], last_name=form.cleaned_data["last_name"],
                employee_id=form.cleaned_data["employee_id"], role=inv.role,
                department=inv.department, manager=inv.manager,
            )
            inv.accepted_at = timezone.now()
            inv.save(update_fields=["accepted_at", "updated_at"])
        record(user, "invitation.accepted", inv, email=inv.email)
        messages.success(request, "Account created. Please sign in.")
        return redirect("login")
    return render(request, "form_page.html", {
        "form": form, "title": f"Create your account ({inv.email})", "submit_label": "Create account",
        "intro": f"You were invited as {inv.get_role_display()}.", "public": True,
    })


@require_roles(Role.SUPER_ADMIN)
def audit_log(request):
    logs = AuditLog.objects.select_related("actor")
    action = request.GET.get("action", "").strip()
    if action:
        logs = logs.filter(action__startswith=action)
    page = Paginator(logs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/audit_log.html", {"page": page, "action": action})
