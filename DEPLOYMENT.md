# Deployment guide

This guide covers deploying the portal with Docker Compose on one Ubuntu server behind an existing reverse proxy
(Nginx or Portainer). Run it in order. Keep real secrets out of Git.

## 1. Prerequisites

- Ubuntu server with Docker Engine and the Compose plugin (`docker compose version`).
- DNS records pointing at the server: `portal.<domain>` (web UI), `api.<domain>` (API for mobile and integrations),
  and `n8n.<domain>` (n8n).
- TLS certificates for those names, terminated at the reverse proxy.
- An SMTP account for sending invitations and sign-in codes.
- Microsoft Entra application (for admin SSO and, later, Microsoft 365 user operations), if you use them.

## 2. Get the code

```bash
git clone https://github.com/Detechpro/technosat-itsm.git /opt/technosat-itsm
cd /opt/technosat-itsm
cp .env.example .env
```

## 3. Fill in `.env`

Set every value. Generate secrets with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | Long random string (required) |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `portal.<domain>` (the compose file adds `api` itself) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://portal.<domain>` |
| `PORTAL_BASE_URL` | `https://portal.<domain>` |
| `PUBLIC_URL` | `https://portal.<domain>` |
| `POSTGRES_PASSWORD` | Long random string |
| `SMTP_*`, `SMTP_FROM` | Your mail provider settings |
| `M365_MODE` | Keep `dry_run` until the tenant test passes |
| `M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET` | From the Entra application (needed for admin SSO) |
| `N8N_WEBHOOK_SECRET`, `N8N_INBOUND_SECRET` | Two different long random strings |
| `N8N_HOST`, `N8N_WEBHOOK_URL` | `n8n.<domain>` and `https://n8n.<domain>/` |

`.env` is ignored by Git and by the Docker build context, so it stays on the server only.

## 4. Start the stack

```bash
docker compose up -d --build
docker compose ps                       # all services should be running
docker compose logs api --tail=50       # migrations should have applied
docker compose exec api python manage.py createsuperuser
```

The `api` container runs migrations on start. The `worker` container retries webhooks and checks overdue
tickets every minute. The `web` container calls the API at `http://api:8000`.

After the superuser exists, sign in to the Django admin at `https://portal.<domain>/admin/` (or through the
API host, if you prefer) and set that user's role to Super Administrator. Then invite the first IT staff members
from the portal.

## 5. Reverse proxy

Point the proxy at the containers. Container ports are not published to the host, so the proxy must run on the
same Docker network or you must publish the ports on `127.0.0.1` only.

| Public host | Container |
|---|---|
| `portal.<domain>` | `web:3000` |
| `api.<domain>` | `api:8000` |
| `n8n.<domain>` | `n8n:5678` |

Forward `X-Forwarded-Proto` and `Host`. Force HTTPS.

## 6. Microsoft Entra (admin sign-in)

In the Entra application, add this redirect URI under Web platform:
`https://portal.<domain>/sso/microsoft/callback`.

Only administrator roles and superusers can sign in with Microsoft, and accounts must already exist in the portal.

Keep `M365_MODE=dry_run`. Test the connection from **Administration > Microsoft 365** before switching to live mode.

## 7. n8n

1. Open `https://n8n.<domain>` and create the owner account.
2. Import `n8n/portal-events-workflow.json` and `n8n/intake-email-teams-workflow.json` as inactive drafts.
3. Attach the SMTP credential to the notification nodes. Leave Outlook and Teams nodes disabled until those are connected.
4. Register the webhook URL in the portal (`https://api.<domain>/...`, see `n8n/README.md`) with the outbound secret.
5. Test with a sample ticket, then activate the workflows.

## 8. Verify

- `https://portal.<domain>/login` loads and sends a sign-in code to a test account.
- `https://api.<domain>/api/v1/dashboard/` returns 401 without a token.
- A test ticket created in the portal appears in n8n's execution list.
- Sign-in attempts and ticket changes appear in the audit log.
- `docker compose exec api python manage.py check --deploy` shows no unexpected warnings.

## 9. Backups and updates

Back up the database daily from the host and copy the output off the server:

```bash
docker compose exec -T db pg_dump -U itsm itsm | gzip > /var/backups/itsm-$(date +%F).sql.gz
```

Also back up the `media` volume (uploaded attachments) and the `n8ndata` volume.

To update:

```bash
cd /opt/technosat-itsm && git pull
docker compose up -d --build
```

## 10. Known limits before go-live

- **Rate limits are per process.** Sign-in code limits use Django's default in-memory cache, and the API runs
  three Gunicorn workers, so the effective limit is up to three times the configured one. Add a shared cache
  (Redis or database cache) before relying on the limit.
- **SLA dates for old tickets.** Tickets created before SLA tracking have no SLA dates and need a one-time
  backfill.
- **Microsoft 365 and Teams.** Live Graph operations and the Outlook and Teams intake are not tested against a
  tenant.
- **Docker images.** The images are built from the Dockerfiles in this repository; the first build on the server
  is the first full build test.
