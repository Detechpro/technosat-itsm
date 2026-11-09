from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts import api as account_api
from integrations.urls import urlpatterns as integration_urls

from .api import ApprovalViewSet, DashboardView, OnboardingCreateView, TaskViewSet, TicketViewSet

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")
router.register("approvals", ApprovalViewSet, basename="approval")
router.register("tasks", TaskViewSet, basename="task")

urlpatterns = [
    path("auth/token/", account_api.obtain_token, name="api_token"),
    path("auth/me/", account_api.me, name="api_me"),
    path("auth/logout/", account_api.logout_token, name="api_logout"),
    path("auth/sso/start/", account_api.sso_start, name="api_sso_start"),
    path("auth/sso/exchange/", account_api.sso_exchange, name="api_sso_exchange"),
    path("dashboard/", DashboardView.as_view(), name="api_dashboard"),
    path("users/", account_api.UserDirectoryView.as_view(), name="api_users"),
    path("lifecycle/onboarding/", OnboardingCreateView.as_view(), name="api_onboarding"),
    path("", include(integration_urls)),
    path("", include(router.urls)),
]
