# Technosat IT Service Portal (ITSM)

A Django + Django REST Framework service desk for Technosat, with a Next.js web app, bilingual
English and Arabic screens and tickets, role-based access, email code sign-in, SLA tracking per
priority, approval-gated employee onboarding and offboarding, IT asset tracking, audit logging, and an
optional Microsoft 365 (Graph) integration that runs in dry-run mode until you configure credentials.

## What is included

| Area | Status |
|---|---|
| Web sign-in by email one-time code (6 digits, 10-minute expiry, 5 attempts, 60-second resend cooldown, single use) | Working, tested end to end |
| Microsoft Entra SSO for administrators (msal) | Built; **not tested against a live tenant** |
| Django admin sign-in | Still password-based |
| Invitations (email link, 7-day expiry, hashed tokens, resend, revoke) | Working |
| Session expiry, login history, audit of sign-in success and failure | Working |
| Roles: Super Admin, IT Admin, Technician, HR Admin, Manager, Asset Manager, Employee | Enforced in views, querysets and API |
| Tickets: auto numbers (IT-YYYY-NNNNN), statuses, priorities, comments, internal notes, attachments, assignment, reopen, CSV export | Working |
| Bilingual tickets: English and Arabic title and details, source language, Arabic labels | Working |
| Bilingual UI: English, Arabic (RTL), or both; each user saves a preferred language | Working |
| SLA per priority (ITIL-based): response and resolution targets, met, breached, running and at-risk states | Working, tested |
| SLA targets editable by administrators (`SlaPolicy` in the Django admin) | Working |
| Onboarding / offboarding: approval first, then 7 / 8 generated tasks | Working |
| Approvals with decision history and timestamps | Working (single level) |
| Dashboard: 7, 30 or 90-day period, KPI tiles, latest tickets, status breakdown, SLA summary, quick actions | Working |
| Technosat front page (services, why Technosat, products, contact) | Working, EN and AR |
| Asset inventory: create, assign, record return | Working |
| Audit log (actions, login success and failure) | Working |
| REST API: `/api/v1/tickets/` (scoped), tickets, approvals, tasks, dashboard, onboarding | Working, tested |
| Microsoft Graph: test connection, create user, assign license, disable account, revoke sessions | Built; **not tested against a live tenant** |
| SMTP (invitations, sign-in codes) | Configured through environment variables |
| n8n outbound webhooks (signed, delivery log, retry with backoff, overdue events) | Working, tested against a local receiver |
| n8n inbound callbacks (signed, replay-protected, add comment / set status) | Working, tested end to end |
| n8n starter workflows (`n8n/`) | Written, **not imported into a live n8n instance** |
| Email and Microsoft Teams intake | Deferred until Outlook and Teams are connected |
| Installable web app (PWA manifest) | Working for Android and iOS home-screen install |
| Native Android / iOS apps | Not built (see below) |

Not yet implemented: SLA business-hours calendars, SLA breach notifications, pausing the SLA clock during
approvals, production backfill of SLA dates for tickets created before SLA tracking, Celery/Redis (a
`worker` container loops over `retry_webhooks` and `check_overdue` instead), scheduled offboarding at the
termination time, a visual workflow builder, Excel export, MFA enrolment, multi-level approvals beyond one
manager, push notifications, and an admin UI for the service catalog. The Django server-rendered pages
still exist alongside the Next.js app (keep one or remove the other).

## Next.js web app (`web/`)

```bash
cd web && npm install
API_BASE_URL=http://127.0.0.1:8000 npm run dev     # http://localhost:3000
```

`API_BASE_URL` is the Django origin only, without `/api/v1` (the app adds that path itself).

The browser never calls Django directly. Server components and server actions call `/api/v1` with a
token that sits in an httpOnly cookie, so the token is not readable from JavaScript. Forms use server
actions and report errors through `?error=` and `?ok=` query parameters, so they work without client JavaScript.

Sign-in is two steps: the user enters an email address, the API emails a six-digit code, and the user enters
it to receive a session. The API answers the email request the same way whether or not the account exists, so
it does not reveal which addresses are registered. Sessions last 8 hours. The OTP endpoints use their own
rate limit (10 requests per minute per IP). In production, configure a shared cache so the limit holds across
workers.

Language and display preferences are stored in cookies (`itsm_lang`, `itsm_display`) and, when signed in,
saved to the user's account.

For a production build: `npm run build && npm run start`.

## Ticket dashboard

The dashboard at `/dashboard` takes `?days=7`, `?days=30` or `?days=90` (default 30) and returns, for that
period, the total, resolved count, status breakdown, category and priority breakdown, and average resolution
time. Open, overdue, SLA-breached and at-risk counts always reflect the current state.

## SLA

Default targets, following ITIL practice:

| Priority | Respond within | Resolve within |
|---|---|---|
| Critical | 15 minutes | 4 hours |
| High | 1 hour | 8 hours |
| Medium | 4 hours | 1 day |
| Low | 8 hours | 3 days |

The response clock stops at the first reply from IT staff that is not an internal note. The resolution clock stops
when a ticket is resolved, closed or cancelled. A ticket is "at risk" when its next SLA deadline falls within two
hours. Administrators can change the targets for each priority in the Django admin under **SLA policies**.

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

Setup steps are in `n8n/README.md`. The workflows there have not been imported into a live n8n instance.

## Mobile (Android and iOS)

Today: the web app is installable from the browser (Android: Chrome "Install app"; iOS: Safari "Add to Home Screen").
Native apps: the API is ready for them. Authenticate with `POST /api/v1/auth/token/`, store the token in the
platform keychain (Android Keystore, iOS Keychain), and send `Authorization: Token <key>`. The recommended path is
Expo (React Native), one codebase for both platforms. It would reuse the same endpoints. Push notifications
are not built. Add them through n8n (FCM for Android and APNs for iOS) once the apps exist.

## Brand

The Technosat logos are in `web/public/brand/` (`technosat-logo-en.png`, `technosat-logo-ar.png`). Colours and
product names are set in `web/lib/brand.ts`. A reversed logo for dark surfaces is still to be supplied.

## Quick start (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_SECRET_KEY=dev-change-me DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser        # then set role to "Super Administrator" in the admin or shell
python manage.py runserver
python manage.py test accounts tickets integrations
```

Open http://localhost:8000 and sign in. In development, emails (invitations and sign-in codes) print to the console.

## Production (Docker Compose on an Ubuntu VPS)

```bash
cp .env.example .env                    # fill in every value
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Put your existing Nginx (or Portainer-managed proxy) in front of the `web` service on port 8000,
terminate TLS there, and forward `X-Forwarded-Proto`. Set `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS` to your public hostname. Sign-in codes need SMTP configured to reach real inboxes.

Back up the database with `docker compose exec db pg_dump -U itsm itsm > backup.sql`. Schedule this
with cron on the host and copy the output off the server.

After upgrading an existing installation, run `python manage.py migrate`. Tickets created before SLA tracking
have no SLA dates; they need a one-time backfill before their SLA figures are meaningful.

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

Administrator sign-in with Microsoft (SSO) uses the same Entra application and the same `M365_TENANT_ID`,
`M365_CLIENT_ID` and `M365_CLIENT_SECRET`. Add this redirect URI to the application:
`<PUBLIC_URL>/sso/microsoft/callback`. SSO never creates accounts: the person must already have an active portal user,
and only administrator roles (`ALLOWED_SSO_ROLES` in `accounts/api.py`) and superusers can sign in with Microsoft.

## Security notes

- Invitation tokens are random, single-use and stored as SHA-256 hashes. Sign-in codes are stored as keyed HMAC-SHA256 hashes, expire after ten minutes, lock after five wrong attempts, and are single use.
- All secrets come from environment variables. The database stores no SMTP or Graph secrets.
- Permissions are enforced on the server for every page, action and API query.
- Uploads are limited by extension and size (`MAX_UPLOAD_SIZE`, default 10 MB). Files are served only to users who can view the ticket.
- Audit records are written for approvals, status changes, invitations, account changes, asset moves, sign-in attempts and M365 runs.
- Set `DJANGO_DEBUG=0` in production. Settings refuse to start without `DJANGO_SECRET_KEY` in that mode.
- Before go-live, run `python manage.py check --deploy` and review the warnings.

## Layout

```
accounts/   users, departments, invitations, sign-in codes (otp.py), SSO (sso.py), audit log, RBAC helpers
tickets/    tickets, bilingual fields, SLA (sla.py), tasks, approvals, lifecycle requests, assets, services, API
integrations/microsoft365.py   Graph client with dry-run and retry handling
integrations/               n8n webhooks and callbacks
n8n/        workflow exports and setup notes
web/        Next.js app: app/ (pages and server actions), components/, lib/ (API client, i18n, brand, prefs)
templates/  server-rendered Django UI
docs/screens/   screenshots from before the Technosat redesign
```
