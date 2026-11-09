# n8n flows

`portal-events-workflow.json` is a starter importable into n8n (Workflows > Import from file).

Setup in n8n:
1. Create environment variables in n8n: `PORTAL_OUTBOUND_SECRET`, `PORTAL_INBOUND_SECRET`,
   `PORTAL_BASE_URL`, `PORTAL_FROM_EMAIL`. Use the same values as the portal's
   `N8N_WEBHOOK_SECRET` (outbound) and `N8N_INBOUND_SECRET` (inbound).
2. Activate the workflow and copy the production webhook URL.
3. In the portal, create a webhook endpoint (Django admin, Integrations > Webhook endpoints) with that URL and
   the event types `approval.requested`, `ticket.overdue`, `lifecycle.completed`.
4. Set the portal's `N8N_WEBHOOK_SECRET` in `.env` to the same value you used for `PORTAL_OUTBOUND_SECRET`.
5. Run `python manage.py retry_webhooks` every minute (cron) and `python manage.py check_overdue` hourly.

Recipient: the email goes to `PORTAL_APPROVER_EMAIL`, a single address. Map it to a per-manager lookup
(for example from a Microsoft 365 or HR table) before production use. Every event payload carries usernames,
not email addresses.

Caveats: this file was written by hand and has not been imported into a running n8n instance here. Node names
and the `if`/`switch` parameter shapes differ between n8n versions, so import it and fix any node the editor
flags. The signature check uses `rawBody`; enable "Raw body" on the Webhook node if your version doesn't
provide it.

## Email and Teams intake

`intake-email-teams-workflow.json` opens a ticket for every new email to the service desk mailbox and every
new message in the chosen Teams channel. Each message goes to `ticket.create_from_message` with a signed
callback. Senders must match an active portal user, so only invited staff can open tickets this way. Unknown
senders get a reply asking for an invitation. Duplicate messages are ignored by event ID.

Set `PORTAL_TEAMS_TEAM_ID` and `PORTAL_TEAMS_CHANNEL_ID` in n8n. Connect Microsoft Outlook and Microsoft Teams
credentials there. The mailbox trigger reads the mailbox that n8n is connected to. The JSON was written by hand
and has not been run against a real mailbox or Teams channel.
