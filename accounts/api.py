from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import Role, User


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    is_global_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "display_name", "role", "role_label", "is_global_admin",
                  "department", "manager"]


class LoginThrottle(AnonRateThrottle):
    rate = "10/minute"


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def obtain_token(request):
    """Exchange username and password for an API token. Used by the Next.js server and mobile apps."""
    throttle = LoginThrottle()
    if not throttle.allow_request(request, None):
        return Response({"error": {"code": "throttled", "message": "Too many attempts. Try again shortly."}},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)
    user = authenticate(request, username=request.data.get("username", ""), password=request.data.get("password", ""))
    if user is None or not user.is_active:
        return Response({"error": {"code": "invalid_credentials", "message": "Username or password is incorrect."}},
                        status=status.HTTP_401_UNAUTHORIZED)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_token(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


class UserDirectoryView(APIView):
    """Active staff who can be chosen as approvers. Only admins and HR can list the directory."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_global_admin or request.user.role == Role.HR_ADMIN):
            raise PermissionDenied("Only administrators and HR can browse the directory.")
        qs = User.objects.filter(is_active=True).order_by("first_name", "username")
        if request.query_params.get("approvers") == "1":
            qs = qs.filter(role__in=[Role.MANAGER, Role.IT_ADMIN, Role.SUPER_ADMIN])
        return Response([{"id": u.pk, "display_name": u.display_name, "role": u.role,
                          "role_label": u.get_role_display()} for u in qs])


ALLOWED_SSO_ROLES = {Role.SUPER_ADMIN, Role.IT_ADMIN}


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def sso_start(request):
    """Body: {"redirect_uri": "..."}. Returns the Microsoft sign-in URL and a state value."""
    from . import sso
    from django.conf import settings as dj
    from .audit import record
    redirect_uri = request.data.get("redirect_uri", "")
    if not redirect_uri.startswith(dj.PORTAL_BASE_URL.rstrip("/") + "/"):
        return Response({"error": {"code": "bad_redirect", "message": "Redirect URI is not allowed."}},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        url, state = sso.start(redirect_uri)
    except RuntimeError as exc:
        return Response({"error": {"code": "sso_not_configured", "message": str(exc)}},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"auth_url": url, "state": state})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def sso_exchange(request):
    """Body: {"code": "...", "redirect_uri": "..."}. Returns a portal API token for an allowed admin."""
    from . import sso
    from .audit import record
    try:
        email = sso.exchange(request.data.get("code", ""), request.data.get("redirect_uri", ""))
    except (ValueError, RuntimeError) as exc:
        record(None, "auth.sso_failed", None, reason=str(exc)[:200])
        return Response({"error": {"code": "sso_failed", "message": "Microsoft sign-in could not be completed."}},
                        status=status.HTTP_401_UNAUTHORIZED)
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None or (user.role not in ALLOWED_SSO_ROLES and not user.is_superuser):
        record(None, "auth.sso_denied", None, email=email)
        return Response({"error": {"code": "not_allowed",
                                  "message": "This Microsoft account does not have administrator access to the portal."}},
                        status=status.HTTP_403_FORBIDDEN)
    token, _ = Token.objects.get_or_create(user=user)
    record(user, "auth.sso_login", user, method="entra")
    return Response({"token": token.key, "user": UserSerializer(user).data})
