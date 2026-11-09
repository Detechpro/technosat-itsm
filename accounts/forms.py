from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Department, Role, User


class InviteForm(forms.Form):
    email = forms.EmailField(help_text="The invitation link is sent to this address. Any email domain is accepted.")
    role = forms.ChoiceField(choices=Role.choices)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False)
    manager = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("first_name", "username"),
        required=False, label="Reporting manager")


class AcceptInviteForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    employee_id = forms.CharField(max_length=40, required=False)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p1 != p2:
            self.add_error("password2", "The passwords do not match.")
        elif p1:
            try:
                validate_password(p1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned
