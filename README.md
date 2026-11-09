# IT Service Portal (ITSM)

A Django + Django REST Framework service desk with role-based access, invitation-based onboarding,
approval-gated employee onboarding/offboarding, IT asset tracking, audit logging and an optional
Microsoft 365 (Graph) integration that runs in dry-run mode until you configure credentials.

## What is included

| Area | Status |
|---|---|
| Invitations (email link, 7-day expiry, hashed tokens, resend, revoke) | Working |
| Login, logout, password reset (SMTP), session expiry, login history | Working |
| Roles: Super Admin, IT Admin, Technician, HR Admin, Manager, Asset Manager, Employee | Enforced in views and querysets |
| Tickets: auto numbers (IT-YYYY-00001), statuses, priorities, comments, internal notes, attachments, assignment, reopen, CSV export | Working |
| Onboarding / offboarding: approval first, then 7 / 8 generated tasks | Working |
| Approvals with decision history and timestamps | Working (single level) |
| Dashboard with DB-backed counts, filters, technician workload, overdue tasks | Working |
| Asset inventory: create, assign, record return | Working |
| Audit log (actions, login success/failure) | Working |
| REST API: `/api/v1/tickets/` (read-only, scoped) | Working |
| Microsoft Graph: test connection, create user, assign license, disable account, revoke sessions | Built; **not tested against a live tenant** |
| SMTP | Configured through environment variables |
| Next.js web app (App Router, server-side API calls, httpOnly session cookie) | Working: dashboard, tickets, new request, ticket detail, onboarding, approvals, tasks |
| Token REST API for web and mobile (`/api/v1/auth/token/`, tickets, approvals, tasks, dashboard, onboarding) | Working, tested |
| n8n outbound webhooks (signed, delivery log, retry with backoff, overdue events) | Working, tested against a local receiver |
| n8n inbound callbacks (signed, replay-protected, add comment / set status) | Working, tested end to end |
| n8n starter workflow (`n8n/portal-events-workflow.json`) | Written, **not imported into a live n8n instance** |
| Installable web app (PWA manifest) | Working for Android and iOS home-screen install |
| Native Android / iOS apps | Not built (see below) |

Not yet implemented: the Django server-rendered pages still exist alongside the Next.js app (keep one
or remove the other), Celery/Redis (a `worker` container loops over `retry_webhooks` and `check_overdue`
instead), scheduled offboarding at the termination time, a visual workflow builder, configurable SLA
policies, Excel export, MFA enrolment, multi-level approvals beyond one manager, push notifications, and
an admin UI for the service catalog. The Next.js app covers the core staff flows, not every admin screen.

## Next.js web app (`web/`)

```bash
cd web && npm install
API_BASE_URL=http://localhost:8000 npm run dev      # http://localhost:3000
```

The browser never calls Django directly. Server components and server actions call `/api/v1` with a
token that sits in an httpOnly cookie, so the token is not readable from JavaScript. Forms use server
actions and report errors through `?error=` and `?ok=` query parameters, so they work without client JavaScript.
Sessions last 8 hours. The sign-in form is rate-limited on the API side (10 attempts per minute per IP).

## n8n

Outbound: every domain event (`ticket.created`, `approval.requested`, `approval.approved`,
`approval.rejected`, `ticket.status_changed`, `ticket.assigned`, `task.completed`, `lifecycle.completed`,
`ticket.overdue`) is queued after the database commit and POSTed to each subscribed webhook endpoint.
Each request carries `X-Portal-Signature: sha256=HMAC(secret, "<timestamp>.<body>")`, `X-Portal-Timestamp`,
`X-Portal-Event` and `X-Portal-Event-Id`. Failed sends retry with exponential backoff up to six attempts,
and every attempt is recorded in the delivery log (Django admin).

Inbound: n8n calls `POST /api/v1/integrations/n8n/callback/` with the same signing scheme and an
`X-Event-Id` header. Supported actions are `ticket.add_comment` and `ticket.set_status`. Timestamps older
than five minutes are rejected, and each event ID is applied once.

Setup steps are in `n8n/README.md`. The workflow there was written by hand and has not been run in n8n.

## Mobile (Android and iOS)

Today: the web app is installable from the browser (Android: Chrome "Install app"; iOS: Safari "Add to Home Screen").
Native apps: the API is ready for them. Authenticate with `POST /api/v1/auth/token/`, store the token in the
platform keychain (Android Keystore, iOS Keychain), and send `Authorization: Token <key>`. The recommended path is
Expo (React Native), one codebase for both platforms. It would reuse the same endpoints. Push notifications
are not built. Add them through n8n (FCM for Android and APNs for iOS) once the apps exist.

## Quick start (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_SECRET_KEY=dev-change-me DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser        # then set role to "Super Administrator" in the admin or shell
python manage.py runserver
python manage.py test tickets accounts
```

Open http://localhost:8000 and sign in. In development, emails print to the console.

## Production (Docker Compose on an Ubuntu VPS)

```bash
cp .env.example .env                    # fill in every value
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Put your existing Nginx (or Portainer-managed proxy) in front of the `web` service on port 8000,
terminate TLS there, and forward `X-Forwarded-Proto`. Set `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS` to your public hostname.

Back up the database with `docker compose exec db pg_dump -U itsm itsm > backup.sql`. Schedule this
with cron on the host and copy the output off the server.

## Microsoft 365 setup

1. In Entra ID, register an application and create a client secret.
2. Grant **application** permissions with admin consent. The connection test only needs
   `Organization.Read.All`. Live user operations need `User.ReadWrite.All` (create, disable, sessions) and
   `Directory.ReadWrite.All` (license assignment). Grant those only when you enable live mode, and review
   them against your own least-privilege policy.
3. Set `M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET`, and optionally
   `M365_DEFAULT_LICENSE_SKU_ID`.
4. Keep `M365_MODE=dry_run` and use **Administration > Microsoft 365 > Test connection**.
5. Run one onboarding task in dry-run mode, confirm the message, then set `M365_MODE=live` and repeat on a
   test user before using real employees.

Dry-run results never mark a task as done. Live mode without credentials fails loudly and never reports success.

## Security notes

- Invitation and password-reset tokens are random and single-use. Invitation tokens are stored as SHA-256 hashes.
- All secrets come from environment variables. The database stores no SMTP or Graph secrets.
- Permissions are enforced on the server for every page, action and API query.
- Uploads are limited by extension and size (`MAX_UPLOAD_SIZE`, default 10 MB). Files are served only to users who can view the ticket.
- Audit records are written for approvals, status changes, invitations, account changes, asset moves and M365 runs.
- Set `DJANGO_DEBUG=0` in production. Settings refuse to start without `DJANGO_SECRET_KEY` in that mode.
- Before go-live, run `python manage.py check --deploy` and review the warnings.

## Layout

```
accounts/   users, departments, invitations, audit log, RBAC helpers
tickets/    tickets, tasks, approvals, lifecycle requests, assets, workflow services, API
integrations/microsoft365.py   Graph client with dry-run and retry handling
templates/  server-rendered UI
```
