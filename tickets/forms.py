import os

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from accounts.models import Department, Role, User
from .models import Asset, Category, OffboardingRequest, OnboardingRequest, Priority, Ticket, TicketComment

ALLOWED_UPLOAD_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".docx", ".xlsx", ".csv", ".log", ".zip"}
SELF_SERVICE_CATEGORIES = [c for c in Category.choices if c[0] not in (Category.ONBOARDING, Category.OFFBOARDING)]


def _approver_queryset():
    return User.objects.filter(is_active=True, role__in=[Role.MANAGER, Role.IT_ADMIN, Role.SUPER_ADMIN]) \
        .order_by("first_name", "username")


class TicketForm(forms.ModelForm):
    category = forms.ChoiceField(choices=SELF_SERVICE_CATEGORIES)
    due_date = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    class Meta:
        model = Ticket
        fields = ["title", "description", "category", "priority", "due_date"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise ValidationError("Please give a short but descriptive title (at least 5 characters).")
        return title


class CommentForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=5000, label="Comment")
    is_internal = forms.BooleanField(required=False, label="Internal note (hidden from requester)")


class AttachmentForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        f = self.cleaned_data["file"]
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_UPLOAD_EXT:
            raise ValidationError(f"File type {ext or '(none)'} is not allowed.")
        if f.size > settings.MAX_UPLOAD_SIZE:
            raise ValidationError("File is larger than the allowed size.")
        return f


class OnboardingForm(forms.Form):
    employee_name = forms.CharField(max_length=150)
    employee_id = forms.CharField(max_length=40, required=False)
    personal_email = forms.EmailField(required=False)
    company_email = forms.EmailField(label="Required company email address")
    department = forms.ModelChoiceField(queryset=Department.objects.all())
    job_title = forms.CharField(max_length=120)
    approver = forms.ModelChoiceField(queryset=_approver_queryset(), label="Approving manager")
    joining_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    employment_type = forms.ChoiceField(choices=[("Full-time", "Full-time"), ("Part-time", "Part-time"),
                                                 ("Contractor", "Contractor"), ("Intern", "Intern")])
    office_location = forms.CharField(max_length=120, required=False)
    m365_license = forms.CharField(max_length=120, required=False, label="Microsoft 365 license")
    laptop_required = forms.BooleanField(required=False, initial=True)
    software_requirements = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    special_permissions = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Additional instructions")


class OffboardingForm(forms.Form):
    employee_name = forms.CharField(max_length=150)
    employee_id = forms.CharField(max_length=40, required=False)
    company_email = forms.EmailField()
    department = forms.ModelChoiceField(queryset=Department.objects.all())
    approver = forms.ModelChoiceField(queryset=_approver_queryset(), label="Manager (approver)")
    last_working_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    termination_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
                                         label="Termination date and time")
    mailbox_retention_days = forms.IntegerField(min_value=0, max_value=3650, initial=30)
    forward_to = forms.EmailField(required=False)
    data_transfer_to = forms.EmailField(required=False)
    assigned_equipment = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Additional instructions")


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ["asset_tag", "name", "category", "manufacturer", "model", "serial_number", "purchase_date",
                  "warranty_expires", "purchase_price", "location", "department", "notes"]
        widgets = {"purchase_date": forms.DateInput(attrs={"type": "date"}),
                   "warranty_expires": forms.DateInput(attrs={"type": "date"}),
                   "notes": forms.Textarea(attrs={"rows": 2})}


class AssignAssetForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by("username"))
