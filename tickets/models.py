from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from accounts.models import Department, TimestampedModel


class Category(models.TextChoices):
    ONBOARDING = "onboarding", "Employee Onboarding"
    OFFBOARDING = "offboarding", "Employee Offboarding"
    EMAIL = "email", "Email Services"
    EQUIPMENT = "equipment", "IT Equipment"
    SUPPORT = "support", "IT Support"
    NETWORK_SECURITY = "network_security", "Network and Security"
    SMTP = "smtp", "SMTP Services"
    GENERAL = "general", "General"


class Status(models.TextChoices):
    NEW = "new", "New"
    SUBMITTED = "submitted", "Submitted"
    PENDING_APPROVAL = "pending_approval", "Pending Approval"
    APPROVED = "approved", "Approved"
    ASSIGNED = "assigned", "Assigned"
    IN_PROGRESS = "in_progress", "In Progress"
    WAITING_FOR_USER = "waiting_for_user", "Waiting for User"
    ON_HOLD = "on_hold", "On Hold"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class Priority(models.TextChoices):
    CRITICAL = "critical", "Critical"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


CLOSED_STATUSES = {Status.RESOLVED, Status.CLOSED, Status.REJECTED, Status.CANCELLED}
OPEN_STATUSES = [s for s in Status.values if s not in CLOSED_STATUSES]
# Categories whose work must not start until a manager approves.
APPROVAL_CATEGORIES = {Category.ONBOARDING, Category.OFFBOARDING, Category.EQUIPMENT}


class TicketSequence(models.Model):
    year = models.PositiveIntegerField(primary_key=True)
    last_value = models.PositiveIntegerField(default=0)


def next_ticket_number():
    year = timezone.now().year
    with transaction.atomic():
        seq, _ = TicketSequence.objects.select_for_update().get_or_create(year=year)
        seq.last_value += 1
        seq.save(update_fields=["last_value"])
    return f"IT-{year}-{seq.last_value:05d}"


class Ticket(TimestampedModel):
    number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.GENERAL, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM, db_index=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NEW, db_index=True)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_tickets")
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="approver_of")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="assigned_tickets")
    due_date = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    overdue_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "priority"]), models.Index(fields=["due_date"])]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_ticket_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} {self.title}"

    @property
    def is_open(self):
        return self.status not in CLOSED_STATUSES

    @property
    def is_overdue(self):
        return bool(self.due_date and self.is_open and self.due_date < timezone.now())


class TicketComment(TimestampedModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    body = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Internal notes are hidden from requesters.")

    class Meta:
        ordering = ["created_at"]


def attachment_upload_path(instance, filename):
    return f"tickets/{instance.ticket.number}/{filename}"


class TicketAttachment(TimestampedModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    file = models.FileField(upload_to=attachment_upload_path)
    original_name = models.CharField(max_length=255)


class Approval(TimestampedModel):
    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approvals")
    level = models.PositiveSmallIntegerField(default=1)
    decision = models.CharField(max_length=10, choices=Decision.choices, default=Decision.PENDING)
    comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["level", "created_at"]


class Task(TimestampedModel):
    class TaskStatus(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="tasks")
    status = models.CharField(max_length=15, choices=TaskStatus.choices, default=TaskStatus.TODO)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    sequence = models.PositiveSmallIntegerField(default=0)
    m365_action = models.CharField(max_length=40, blank=True,
                                   help_text="If set, IT admins can run this step as a Microsoft 365 automation.")
    result = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence", "id"]


class OnboardingRequest(TimestampedModel):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="onboarding")
    employee_name = models.CharField(max_length=150)
    employee_id = models.CharField(max_length=40, blank=True)
    personal_email = models.EmailField(blank=True)
    company_email = models.EmailField(help_text="Required company mailbox / UPN for the new employee.")
    job_title = models.CharField(max_length=120)
    joining_date = models.DateField()
    employment_type = models.CharField(max_length=40, default="Full-time")
    office_location = models.CharField(max_length=120, blank=True)
    m365_license = models.CharField(max_length=120, blank=True)
    laptop_required = models.BooleanField(default=True)
    software_requirements = models.TextField(blank=True)
    special_permissions = models.TextField(blank=True)


class OffboardingRequest(TimestampedModel):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="offboarding")
    employee_name = models.CharField(max_length=150)
    employee_id = models.CharField(max_length=40, blank=True)
    company_email = models.EmailField()
    last_working_day = models.DateField()
    termination_at = models.DateTimeField(help_text="Accounts are disabled at this date and time.")
    mailbox_retention_days = models.PositiveIntegerField(default=30)
    forward_to = models.EmailField(blank=True)
    data_transfer_to = models.EmailField(blank=True)
    assigned_equipment = models.TextField(blank=True)


class Asset(TimestampedModel):
    class AssetCategory(models.TextChoices):
        LAPTOP = "laptop", "Laptop"
        DESKTOP = "desktop", "Desktop"
        MONITOR = "monitor", "Monitor"
        KEYBOARD = "keyboard", "Keyboard"
        MOUSE = "mouse", "Mouse"
        PRINTER = "printer", "Printer"
        MOBILE = "mobile", "Mobile device"
        NETWORK = "network", "Network equipment"
        ACCESSORY = "accessory", "Accessory"

    class AssetStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        ASSIGNED = "assigned", "Assigned"
        MAINTENANCE = "maintenance", "Under maintenance"
        RETURNED = "returned", "Returned"
        DAMAGED = "damaged", "Damaged"
        RETIRED = "retired", "Retired"

    asset_tag = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=AssetCategory.choices, default=AssetCategory.LAPTOP)
    manufacturer = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=80, blank=True)
    serial_number = models.CharField(max_length=80, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expires = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=15, choices=AssetStatus.choices, default=AssetStatus.AVAILABLE, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="assets")
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    location = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["asset_tag"]

    def __str__(self):
        return f"{self.asset_tag} {self.name}"
