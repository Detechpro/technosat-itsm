"""Microsoft Entra ID (Azure AD) sign-in for administrators, using the authorization-code flow.

The Next.js app starts the flow and handles the redirect. Django exchanges the code, verifies the
identity, and maps it to an existing active portal user. Users are never created by SSO: invitation is
still required. Only administrator roles (ALLOWED_SSO_ROLES in accounts/api.py) and superusers may sign in with Microsoft.
"""
import secrets

import msal
from django.conf import settings

SCOPES = ["User.Read"]


def _app():
    cfg = settings.MICROSOFT365
    if not (cfg["TENANT_ID"] and cfg["CLIENT_ID"] and cfg["CLIENT_SECRET"]):
        raise RuntimeError("Microsoft Entra SSO is not configured (M365_TENANT_ID, M365_CLIENT_ID, M365_CLIENT_SECRET).")
    return msal.ConfidentialClientApplication(
        cfg["CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{cfg['TENANT_ID']}",
        client_credential=cfg["CLIENT_SECRET"],
    )


def start(redirect_uri):
    """Returns (authorization URL, state). The caller must store state and compare it on return."""
    state = secrets.token_urlsafe(24)
    url = _app().get_authorization_request_url(SCOPES, state=state, redirect_uri=redirect_uri, prompt="select_account")
    return url, state


def exchange(code, redirect_uri):
    """Returns the verified user's email (lower-case) or raises ValueError."""
    result = _app().acquire_token_by_authorization_code(code, scopes=SCOPES, redirect_uri=redirect_uri)
    if "error" in result:
        raise ValueError(result.get("error_description", "Microsoft sign-in failed.").split("\r\n")[0][:200])
    claims = result.get("id_token_claims") or {}
    email = (claims.get("preferred_username") or claims.get("email") or "").strip().lower()
    if not email:
        raise ValueError("Microsoft did not return an email address for this account.")
    return email
