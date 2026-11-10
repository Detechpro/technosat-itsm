# Deploying on Portainer

One Portainer stack runs everything on the same host: PostgreSQL, the Django API, the background worker,
the Next.js web app and n8n. Your existing reverse proxy (Nginx Proxy Manager, Traefik or Portainer's proxy)
publishes the public hostnames.

## 1. Prerequisites

- Portainer with a Docker environment on the Ubuntu server.
- DNS records: `portal.<domain>`, `api.<domain>`, `n8n.<domain>` pointing at the server.
- A reverse proxy container with TLS for those three hostnames.
- SMTP credentials for sign-in codes and invitations.

## 2. Create the stack from Git

1. In Portainer: **Stacks > Add stack > Repository**.
2. Name: `technosat-itsm`.
3. Repository URL: `https://github.com/Detechpro/technosat-itsm`, reference `refs/heads/main`.
4. Compose path: `docker-compose.yml`.
5. **Environment variables:** add every variable from `.env.example`, using real values. Do not commit them.
   Portainer keeps them with the stack, so the repository never holds secrets.
6. Enable **Re-pull image and redeploy** only if you want Portainer to update from Git on each redeploy.
7. **Deploy the stack.** The first build takes several minutes.

Required values, at minimum: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=portal.<domain>`,
`DJANGO_CSRF_TRUSTED_ORIGINS=https://portal.<domain>`, `PORTAL_BASE_URL`, `PUBLIC_URL`, `POSTGRES_PASSWORD`,
`SMTP_*`, `N8N_WEBHOOK_SECRET`, `N8N_INBOUND_SECRET`, `N8N_HOST`, `N8N_WEBHOOK_URL`.

## 3. Database

PostgreSQL 16 runs in the stack as `db`. Its data lives in the named volume `pgdata`, so it survives redeploys.
Do not remove the volume unless you intend to erase the data.

Daily backup, run on the host with cron or a Portainer scheduled job:

```bash
docker exec $(docker ps -qf name=technosat-itsm_db_1) pg_dump -U itsm itsm | gzip > /var/backups/itsm-$(date +%F).sql.gz
```

Copy the backups off the server. Back up the `media` (attachments) and `n8ndata` (n8n workflows and credentials)
volumes as well.

## 4. First start

The `api` container runs migrations on start. In Portainer, open **Containers > technosat-itsm_api_1 > Console**,
choose `/bin/sh`, and run:

```bash
python manage.py createsuperuser
```

Then sign in to `https://portal.<domain>/admin/` with that account and set its role to Super Administrator. Invite the
IT staff from the portal.

## 5. Reverse proxy wiring

The stack does not publish ports to the host. Connect your proxy container to the stack network
(`technosat-itsm_default`) and point the hostnames at these containers:

| Hostname | Container | Port |
|---|---|---|
| `portal.<domain>` | `technosat-itsm_web_1` | 3000 |
| `api.<domain>` | `technosat-itsm_api_1` | 8000 |
| `n8n.<domain>` | `technosat-itsm_n8n_1` | 5678 |

Force HTTPS and forward `X-Forwarded-Proto` and `Host`.

Microsoft sign-in: add `https://portal.<domain>/sso/microsoft/callback` as a redirect URI in the Entra application.

## 6. Giving n8n access to the portal

n8n does not sign in to the portal. The two sides trust each other through two shared secrets, and all calls stay on
the internal Docker network.

**Portal to n8n (events):**
1. In n8n, import `n8n/portal-events-workflow.json`. Copy the path from its Webhook node.
2. In the portal Django admin (**Integrations > Webhook endpoints > Add**):
   - Name: `n8n portal events`
   - URL: `http://n8n:5678/webhook/<path-from-the-webhook-node>`
   - Event types: `["*"]`
   - Secret env: `N8N_WEBHOOK_SECRET`
3. In n8n, the workflow's signature check must use the same value as `N8N_WEBHOOK_SECRET`. Set it as an n8n
   environment variable named `PORTAL_OUTBOUND_SECRET` (the compose file already passes it through).

**n8n to portal (callbacks):**
- The workflow calls `http://api:8000/api/v1/integrations/n8n/callback/` (set by `N8N_PORTAL_URL`).
- It sends `X-Event-Id` (unique per run), `X-Portal-Timestamp`, and `X-Portal-Signature`, signed with
  `N8N_INBOUND_SECRET` (passed to n8n as `PORTAL_INBOUND_SECRET`).
- The portal records the actor as the user `n8n-service`, created automatically with the IT Administrator role and no
  password, so nobody can sign in as it. Review that role in the admin if your policy requires a narrower one.

**Rotating secrets:** change `N8N_WEBHOOK_SECRET` and `N8N_INBOUND_SECRET` in the Portainer stack variables, change the
matching values in n8n, then redeploy both.

**Leave the Outlook and Teams nodes disabled** until those accounts are connected in n8n.

## 7. Verify

- `https://portal.<domain>/login` loads and sends a code to a test account.
- `https://api.<domain>/api/v1/dashboard/` returns 401 without a token.
- Create a test ticket. It should appear in n8n's executions under the Webhook trigger, and the Webhook endpoint's delivery
  log in the admin should show `delivered`.
- A status change made from n8n through the callback should appear in the ticket's conversation.

## 8. Updating

Portainer: **Stacks > technosat-itsm > Pull and redeploy**. The `api` container migrates the database on start. Take a
backup first.

## 9. Known limits

- Sign-in code rate limits are per process (three API workers), so the effective limit is up to three times the
  configured one. Add a shared cache before relying on it.
- Tickets created before SLA tracking need a one-time SLA date backfill.
- Microsoft 365 live operations, Outlook and Teams are not tested against a live tenant.
- Pin the n8n image version in `docker-compose.yml` (it currently uses `latest`) once you choose a version to standardise on.
