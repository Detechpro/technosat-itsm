"""Role-based access control. Enforced in views and querysets, never only in templates."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Role

IT_STAFF_ROLES = {Role.SUPER_ADMIN, Role.IT_ADMIN, Role.TECHNICIAN, Role.ASSET_MANAGER}


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if user.is_superuser or user.role in roles:
                return view(request, *args, **kwargs)
            raise PermissionDenied
        return wrapper
    return decorator


def is_it_staff(user):
    return user.is_superuser or user.role in IT_STAFF_ROLES


def can_manage_users(user):
    return user.is_superuser or user.role == Role.SUPER_ADMIN


def can_invite(user):
    return user.is_superuser or user.role in (Role.SUPER_ADMIN, Role.IT_ADMIN)


def visible_tickets(user):
    """Queryset of tickets the user is allowed to see, scoped by role."""
    from tickets.models import Ticket, Category  # local import avoids app loading cycle

    qs = Ticket.objects.all()
    if user.is_global_admin:
        return qs
    q = Q(requester=user) | Q(assignee=user) | Q(approvals__approver=user) | Q(tasks__assignee=user)
    if user.role == Role.MANAGER and user.department_id:
        q |= Q(department_id=user.department_id)
    if user.role == Role.HR_ADMIN:
        q |= Q(category__in=[Category.ONBOARDING, Category.OFFBOARDING])
    if user.role == Role.ASSET_MANAGER:
        q |= Q(category=Category.EQUIPMENT)
    return qs.filter(q).distinct()


def can_view_ticket(user, ticket):
    return visible_tickets(user).filter(pk=ticket.pk).exists()


def can_assign_tickets(user):
    return user.is_global_admin


def can_change_status(user, ticket):
    """Admins may change any ticket; technicians only the tickets assigned to them."""
    if user.is_global_admin:
        return True
    return user.role == Role.TECHNICIAN and ticket.assignee_id == user.pk


def can_manage_lifecycle(user):
    return user.is_global_admin or user.role == Role.HR_ADMIN
