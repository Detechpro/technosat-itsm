import type { Metadata } from "next";
import Link from "next/link";
import { decideApproval } from "@/app/actions";
import { api } from "@/lib/api";
import { fmtDate, requireUser } from "@/lib/session";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { Flash } from "@/components/Flash";
import type { Approval, Paginated } from "@/lib/types";

export const metadata: Metadata = { title: "Approvals" };

export default async function ApprovalsPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const { token } = await requireUser();
  const { lang } = await getPrefs();
  const ui = dict(lang);
  const sp = await searchParams;
  const [pending, history] = await Promise.all([
    api<Paginated<Approval>>("/approvals/", { token }),
    api<Paginated<Approval>>("/approvals/?decision=approved", { token }),
  ]);
  return (
    <>
      <div className="crumbs">{ui.serviceDesk}</div>
      <h1>{ui.approvals}</h1>
      <Flash ok={sp.ok} error={sp.error} />
      <div className="card">
        <h2>{ui.waitingDecision}</h2>
        {pending.results.length === 0 && <p className="empty">{ui.nothingWaiting}</p>}
        {pending.results.map((a) => (
          <div key={a.id} style={{ borderBottom: "1px solid var(--border)", padding: "12px 0" }}>
            <strong><Link href={`/tickets/${a.ticket}`}>{a.ticket}</Link> {a.ticket_title}</strong>
            <div className="muted">{ui.from} {a.requester} · {a.category.replace("_", " ")} · {fmtDate(a.created_at)}</div>
            <form action={decideApproval.bind(null, a.id)} className="row" style={{ marginTop: 8 }}>
              <input name="comment" placeholder={ui.commentOptional} aria-label={ui.comment} />
              <button className="btn btn-primary auto" name="decision" value="approved" type="submit">{ui.approve}</button>
              <button className="btn btn-danger auto" name="decision" value="rejected" type="submit">{ui.reject}</button>
            </form>
          </div>
        ))}
      </div>
      <div className="card">
        <h2>{ui.approvedByYou}</h2>
        <ul className="timeline">
          {history.results.map((a) => (<li key={a.id}><Link href={`/tickets/${a.ticket}`}>{a.ticket}</Link> {a.ticket_title} <span className="muted">· {fmtDate(a.decided_at)}</span></li>))}
          {history.results.length === 0 && <li className="muted">{ui.noApprovals}</li>}
        </ul>
      </div>
    </>
  );
}
