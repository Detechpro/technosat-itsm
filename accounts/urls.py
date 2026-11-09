from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
        success_url=reverse_lazy("password_reset_done")), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
        success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
    path("invite/<str:token>/", views.accept_invite, name="accept_invite"),
    path("administration/users/", views.user_list, name="user_list"),
    path("administration/users/invite/", views.invite_create, name="invite_create"),
    path("administration/invitations/<int:pk>/resend/", views.invitation_resend, name="invitation_resend"),
    path("administration/invitations/<int:pk>/revoke/", views.invitation_revoke, name="invitation_revoke"),
    path("administration/users/<int:pk>/toggle-active/", views.user_toggle_active, name="user_toggle_active"),
    path("administration/audit-log/", views.audit_log, name="audit_log"),
]
