from django.shortcuts import redirect
from django.urls import path

from . import views


def home(request):
    return redirect("dashboard")


urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("tickets/", views.ticket_list, name="ticket_list"),
    path("tickets/new/", views.ticket_create, name="ticket_create"),
    path("tickets/export.csv", views.ticket_export_csv, name="ticket_export_csv"),
    path("tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path("attachments/<int:pk>/", views.attachment_download, name="attachment_download"),
    path("catalog/", views.catalog, name="catalog"),
    path("my-tasks/", views.my_tasks, name="my_tasks"),
    path("tasks/<int:pk>/update/", views.task_update, name="task_update"),
    path("tasks/<int:pk>/run-m365/", views.task_run_m365, name="task_run_m365"),
    path("approvals/", views.approvals, name="approvals"),
    path("approvals/<int:pk>/decide/", views.approval_decide, name="approval_decide"),
    path("lifecycle/<str:kind>/", views.lifecycle_list, name="lifecycle_list"),
    path("lifecycle/<str:kind>/new/", views.lifecycle_create, name="lifecycle_create"),
    path("assets/", views.asset_list, name="asset_list"),
    path("assets/new/", views.asset_create, name="asset_create"),
    path("assets/<int:pk>/assign/", views.asset_assign, name="asset_assign"),
    path("integrations/microsoft365/", views.m365_status, name="m365_status"),
]
