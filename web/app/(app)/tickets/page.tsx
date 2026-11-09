import type { Metadata } from "next";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmtDate, requireUser } from "@/lib/session";
import { StatusBadge } from "@/components/Status";
import { Flash } from "@/components/Flash";
import type { Paginated, Ticket } from "@/lib/types";
import { STATUS_OPTIONS, PRIORITY_OPTIONS } from "@/lib/types";

export const metadata: Metadata = { title: "Tickets" };

type SP = Record<string, string | undefined>;

export default async function TicketsPage({ searchParams }: { searchParams: Promise<SP> }) {
  const { token } = await requireUser();
  const sp = await searchParams;
  const qs = new URLSearchParams();
  if (sp.q) qs.set("search", sp.q);
  if (sp.status === "open") qs.set("open", "1");
  else if (sp.status) qs.set("status", sp.status);
  if (sp.priority) qs.set("priority", sp.priority);
  if (sp.page) qs.set("page", sp.page);
  if (sp.mine) qs.set("mine", "1");
  const data = await api<Paginated<Ticket>>(`/tickets/?${qs.toString()}`, { token });
  const page = Number(sp.page ?? 1);
  const keep = (n: number) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(sp)) if (v) p.set(k, v);
    p.set("page", String(n));
    return `/tickets?${p.toString()}`;
  };

  return (
    <>
      <div className="topbar">
        <div><div className="crumbs">Service desk</div><h1>{sp.mine ? "My requests" : "Tickets"}</h1></div>
        <Link className="btn btn-primary" href="/tickets/new">+ New request</Link>
      </div>
      <Flash ok={sp.ok} error={sp.error} />
      <div className="card">
        <form className="row" style={{ marginBottom: 12 }}>
          <input type="search" name="q" defaultValue={sp.q} placeholder="Search number, title or description" />
          <select name="status" defaultValue={sp.status ?? ""}>
            <option value="">Any status</option>
            <option value="open">Open</option>
            {STATUS_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          <select name="priority" defaultValue={sp.priority ?? ""}>
            <option value="">Any priority</option>
            {PRIORITY_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          <button className="btn auto" type="submit">Apply</button>
        </form>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Number</th><th>Title</th><th>Priority</th><th>Status</th><th>Requester</th><th>Due</th></tr></thead>
            <tbody>
              {data.results.map((t) => (
                <tr key={t.number}>
                  <td><Link href={`/tickets/${t.number}`}>{t.number}</Link></td>
                  <td>{t.title}{t.is_overdue && <> <StatusBadge value="overdue" label="overdue" /></>}</td>
                  <td>{t.priority_label}</td>
                  <td><StatusBadge value={t.status} label={t.status_label} /></td>
                  <td>{t.requester_name}</td>
                  <td>{t.due_date ? fmtDate(t.due_date) : "—"}</td>
                </tr>
              ))}
              {data.results.length === 0 && <tr><td colSpan={6} className="empty">No tickets match these filters.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          {data.previous && <Link className="btn auto" href={keep(page - 1)}>← Previous</Link>}
          {data.next && <Link className="btn auto" href={keep(page + 1)}>Next →</Link>}
          <span className="muted">{data.count} total</span>
        </div>
      </div>
    </>
  );
}
