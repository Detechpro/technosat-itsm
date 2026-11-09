from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.db.models import Count
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role, User
from accounts.permissions import visible_tickets

from . import services
from .models import (APPROVAL_CATEGORIES, OPEN_STATUSES, Approval, Category, OnboardingRequest, Priority, Status as TStatus,
                     Task, Ticket, TicketComment)


class TicketSerializer(serializers.ModelSerializer):
    requester = serializers.CharField(source="requester.username", read_only=True)
    requester_name = serializers.CharField(source="requester.display_name", read_only=True)
    assignee = serializers.CharField(source="assignee.username", read_only=True, default=None)
    assignee_name = serializers.CharField(source="assignee.display_name", read_only=True, default=None)
    department = serializers.CharField(source="department.name", read_only=True, default=None)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Ticket
        fields = ["number", "title", "description", "category", "category_label", "priority", "priority_label",
                  "status", "status_label", "requester", "requester_name", "assignee", "assignee_name",
                  "department", "due_date", "resolved_at", "closed_at", "created_at", "updated_at", "is_overdue"]
        read_only_fields = ["number", "status", "requester", "assignee", "department", "resolved_at", "closed_at",
                            "created_at", "updated_at"]


class TicketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=5, max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    category = serializers.ChoiceField(choices=[c for c in Category.values if c not in ("onboarding", "offboarding")],
                                       default="general")
    priority = serializers.ChoiceField(choices=Priority.values, default="medium")
    due_date = serializers.DateTimeField(required=False, allow_null=True, default=None)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = TicketComment
        fields = ["id", "author", "body", "is_internal", "created_at"]
        read_only_fields = ["id", "author", "is_internal", "created_at"]


class TaskSerializer(serializers.ModelSerializer):
    ticket = serializers.CharField(source="ticket.number", read_only=True)
    ticket_title = serializers.CharField(source="ticket.title", read_only=True)
    assignee = serializers.CharField(source="assignee.display_name", read_only=True, default=None)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Task
        fields = ["id", "ticket", "ticket_title", "title", "assignee", "status", "status_label", "priority",
                  "due_date", "completed_at", "m365_action", "result"]


class ApprovalSerializer(serializers.ModelSerializer):
    ticket = serializers.CharField(source="ticket.number", read_only=True)
    ticket_title = serializers.CharField(source="ticket.title", read_only=True)
    requester = serializers.CharField(source="ticket.requester.display_name", read_only=True)
    category = serializers.CharField(source="ticket.category", read_only=True)

    class Meta:
        model = Approval
        fields = ["id", "ticket", "ticket_title", "requester", "category", "decision", "comment", "decided_at",
                  "created_at"]


class TicketViewSet(viewsets.ModelViewSet):
    """Tickets scoped to the caller's role. Writes go through the workflow services."""
    serializer_class = TicketSerializer
    lookup_field = "number"
    lookup_value_regex = r"IT-\d{4}-\d{5}"
    http_method_names = ["get", "post", "head", "options"]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["number", "title", "description"]
    ordering_fields = ["created_at", "due_date", "priority", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = visible_tickets(self.request.user).select_related("requester", "assignee", "department")
        for field in ("status", "priority", "category"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        if self.request.query_params.get("open") == "1":
            qs = qs.filter(status__in=OPEN_STATUSES)
        if self.request.query_params.get("mine") == "1":
            qs = qs.filter(requester=self.request.user)
        return qs

    def create(self, request):
        s = TicketCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            ticket = services.create_ticket(request.user, title=d["title"], description=d["description"],
                                            category=d["category"], priority=d["priority"], due_date=d["due_date"])
        except DjangoValidationError as exc:
            raise ValidationError({"category": exc.messages})
        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, number=None):
        ticket = self.get_object()
        if request.method == "GET":
            qs = ticket.comments.select_related("author")
            if not request.user.is_global_admin and request.user.role != Role.TECHNICIAN:
                qs = qs.filter(is_internal=False)
            return Response(CommentSerializer(qs, many=True).data)
        body = str(request.data.get("body", "")).strip()
        if not body:
            raise ValidationError({"body": ["This field is required."]})
        internal = bool(request.data.get("is_internal", False))
        try:
            comment = services.add_comment(ticket, request.user, body[:5000], is_internal=internal)
        except PermissionDenied as exc:
            return Response({"error": {"code": "forbidden", "message": str(exc)}}, status=403)
        return Response(CommentSerializer(comment).data, status=201)

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, number=None):
        ticket = self.get_object()
        new_status = request.data.get("status", "")
        if new_status not in TStatus.values:
            raise ValidationError({"status": ["Unknown status."]})
        return self._call(ticket, lambda t: services.change_status(t, request.user, new_status))

    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request, number=None):
        ticket = self.get_object()
        assignee = User.objects.filter(pk=request.data.get("assignee") or None, is_active=True).first()
        return self._call(ticket, lambda t: services.assign_ticket(t, request.user, assignee))

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, number=None):
        ticket = self.get_object()
        return self._call(ticket, lambda t: services.reopen_ticket(t, request.user))

    def _call(self, ticket, fn):
        try:
            fn(ticket)
        except PermissionDenied as exc:
            return Response({"error": {"code": "forbidden", "message": str(exc)}}, status=403)
        except DjangoValidationError as exc:
            return Response({"error": {"code": "invalid", "message": " ".join(exc.messages)}}, status=422)
        ticket.refresh_from_db()
        return Response(TicketSerializer(ticket).data)


class ApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApprovalSerializer

    def get_queryset(self):
        qs = Approval.objects.select_related("ticket", "ticket__requester")
        if self.request.query_params.get("decision"):
            qs = qs.filter(decision=self.request.query_params["decision"])
        else:
            qs = qs.filter(decision=Approval.Decision.PENDING)
        if not self.request.user.is_global_admin:
            qs = qs.filter(approver=self.request.user)
        return qs

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request, pk=None):
        approval = self.get_object()
        decision = request.data.get("decision")
        if decision not in (Approval.Decision.APPROVED, Approval.Decision.REJECTED):
            raise ValidationError({"decision": ["Use 'approved' or 'rejected'."]})
        try:
            services.decide_approval(approval, request.user, decision, str(request.data.get("comment", ""))[:2000])
        except PermissionDenied as exc:
            return Response({"error": {"code": "forbidden", "message": str(exc)}}, status=403)
        except DjangoValidationError as exc:
            return Response({"error": {"code": "invalid", "message": " ".join(exc.messages)}}, status=422)
        approval.refresh_from_db()
        return Response(ApprovalSerializer(approval).data)


class TaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        qs = Task.objects.select_related("ticket", "assignee")
        if self.request.query_params.get("mine", "1") != "1":
            return qs.filter(ticket__in=visible_tickets(self.request.user))
        qs = qs.filter(assignee=self.request.user)
        if self.request.query_params.get("open") == "1":
            qs = qs.exclude(status=Task.TaskStatus.DONE)
        return qs

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        task = self.get_object()
        try:
            services.complete_task(task, request.user, done=bool(request.data.get("done", True)))
        except PermissionDenied as exc:
            return Response({"error": {"code": "forbidden", "message": str(exc)}}, status=403)
        task.refresh_from_db()
        return Response(TaskSerializer(task).data)


class DashboardView(APIView):
    """Counts for the caller's scope, computed from the database."""

    @staticmethod
    def _pending_approvals(user):
        qs = Approval.objects.filter(decision=Approval.Decision.PENDING)
        return qs.count() if user.is_global_admin else qs.filter(approver=user).count()

    def get(self, request):
        base = visible_tickets(request.user)
        now = timezone.now()
        data = {
            "total": base.count(),
            "open": base.filter(status__in=OPEN_STATUSES).count(),
            "in_progress": base.filter(status=TStatus.IN_PROGRESS).count(),
            "resolved": base.filter(status=TStatus.RESOLVED).count(),
            "overdue": base.filter(due_date__lt=now, status__in=OPEN_STATUSES).count(),
            "pending_approvals": self._pending_approvals(request.user),
            "my_open_tasks": Task.objects.filter(assignee=request.user).exclude(status=Task.TaskStatus.DONE).count(),
            "by_category": list(base.values("category").annotate(n=Count("id")).order_by("-n")),
            "by_priority": list(base.values("priority").annotate(n=Count("id")).order_by("-n")),
        }
        return Response(data)


class OnboardingCreateSerializer(serializers.Serializer):
    employee_name = serializers.CharField(max_length=150)
    employee_id = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    company_email = serializers.EmailField()
    personal_email = serializers.EmailField(required=False, allow_blank=True, default="")
    job_title = serializers.CharField(max_length=120)
    joining_date = serializers.DateField()
    employment_type = serializers.CharField(max_length=40, default="Full-time")
    office_location = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    m365_license = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    laptop_required = serializers.BooleanField(default=True)
    software_requirements = serializers.CharField(required=False, allow_blank=True, default="")
    special_permissions = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    approver = serializers.IntegerField()


class OnboardingCreateView(APIView):
    def post(self, request):
        if not (request.user.is_global_admin or request.user.role == Role.HR_ADMIN):
            raise PermissionDenied("Only HR or IT administrators can submit onboarding requests.")
        s = OnboardingCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = dict(s.validated_data)
        approver = User.objects.filter(pk=d.pop("approver"), is_active=True).first()
        if approver is None:
            raise ValidationError({"approver": ["Choose an active approving manager."]})
        ticket_data = {"approver": approver, "due_date": None}
        try:
            ticket = services.create_onboarding(request.user, ticket_data=ticket_data, details=d)
        except DjangoValidationError as exc:
            raise ValidationError({"approver": exc.messages})
        return Response({"number": ticket.number, "status": ticket.status}, status=201)
