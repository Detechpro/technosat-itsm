import type { Metadata } from "next";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmtDate, requireUser } from "@/lib/session";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { StatusBadge } from "@/components/Status";
import { SlaBadge } from "@/components/SlaBadge";
import { Flash } from "@/components/Flash";
import { BilingualText } from "@/components/BilingualText";
import type { Dashboard, Paginated, Ticket } from "@/lib/types";
import { STATUS_OPTIONS, PRIORITY_OPTIONS } from "@/lib/types";

export const metadata: Metadata = { title: "Tickets" };

type SP = Record<string, string | undefined>;

export default async function TicketsPage({ searchParams }: { searchParams: Promise<SP> }) {
  const { token } = await requireUser();
  const { lang, display } = await getPrefs();
  const ui = dict(lang);
  const sp = await searchParams;
  const qs = new URLSearchParams();
  if (sp.q) qs.set("search", sp.q);
  if (sp.status === "open") qs.set("open", "1");
  else if (sp.status) qs.set("status", sp.status);
  if (sp.priority) qs.set("priority", sp.priority);
  if (sp.page) qs.set("page", sp.page);
  if (sp.mine) qs.set("mine", "1");
  const data = await api<Paginated<Ticket>>(`/tickets/?${qs.toString()}`, { token });
  const summary = await api<Dashboard>("/dashboard/", { token }).catch(() => null);
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
        <div><div className="crumbs">{ui.serviceDesk}</div><h1>{sp.mine ? ui.myRequests : ui.tickets}</h1></div>
        <Link className="btn btn-primary" href="/tickets/new">+ {ui.newRequest}</Link>
      </div>
      <Flash ok={sp.ok} error={sp.error} />
      {summary?.sla && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>{ui.slaTitle}</h2>
          <div className="sla-grid">
            <div className="card stat"><div className="n">{summary.sla.response_breached}</div><div className="l">{ui.slaResponseBreached}</div></div>
            <div className="card stat"><div className="n">{summary.sla.resolution_breached}</div><div className="l">{ui.slaResolutionBreached}</div></div>
            <div className="card stat"><div className="n">{summary.sla.at_risk}</div><div className="l">{ui.slaAtRiskCount}</div></div>
            <div className="card stat"><div className="n">{summary.sla.met_percent === null ? "—" : `${summary.sla.met_percent}%`}</div><div className="l">{ui.slaMetPercent}</div></div>
          </div>
        </div>
      )}
      <div className="card">
        <form className="row" style={{ marginBottom: 12 }}>
          <input type="search" name="q" defaultValue={sp.q} placeholder={ui.search} />
          <select name="status" defaultValue={sp.status ?? ""}>
            <option value="">{ui.anyStatus}</option>
            <option value="open">{ui.open}</option>
            {STATUS_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{ui.statusNames[v] ?? l}</option>))}
          </select>
          <select name="priority" defaultValue={sp.priority ?? ""}>
            <option value="">{ui.anyPriority}</option>
            {PRIORITY_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          <button className="btn auto" type="submit">{ui.apply}</button>
        </form>
        <div className="table-wrap">
          <table>
            <thead><tr><th>{ui.number}</th><th>{ui.title}</th><th>{ui.priority}</th><th>{ui.status}</th><th>{ui.requester}</th><th>{ui.resolveBy}</th><th>{ui.slaTitle}</th></tr></thead>
            <tbody>
              {data.results.map((t) => (
                <tr key={t.number}>
                  <td><Link href={`/tickets/${t.number}`}>{t.number}</Link></td>
                  <td>
                    <BilingualText en={t.title} ar={t.title_ar} display={display} primary={t.source_language ?? "en"} />
                    {t.is_overdue && <> <StatusBadge value="overdue" label={ui.overdue} /></>}
                  </td>
                  <td>{lang === "ar" ? t.priority_label_ar ?? t.priority_label : t.priority_label}</td>
                  <td><StatusBadge value={t.status} label={ui.statusNames[t.status] ?? t.status_label} /></td>
                  <td>{t.requester_name}</td>
                  <td>{t.sla_resolution_due ? fmtDate(t.sla_resolution_due) : "—"}</td>
                  <td><SlaBadge state={t.sla_resolution_status} lang={lang} /></td>
                </tr>
              ))}
              {data.results.length === 0 && <tr><td colSpan={7} className="empty">{ui.noTickets}</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          {data.previous && <Link className="btn auto" href={keep(page - 1)}>{ui.previous}</Link>}
          {data.next && <Link className="btn auto" href={keep(page + 1)}>{ui.next}</Link>}
          <span className="muted">{data.count} {ui.total}</span>
        </div>
      </div>
    </>
  );
}
