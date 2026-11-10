import type { Metadata } from "next";
import Link from "next/link";
import { api } from "@/lib/api";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/session";
import { SlaBadge } from "@/components/SlaBadge";
import { BilingualText } from "@/components/BilingualText";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import type { Dashboard, Paginated, Ticket } from "@/lib/types";
import s from "./dashboard.module.css";

export const metadata: Metadata = { title: "Dashboard" };

const PERIODS = ["7", "30", "90"] as const;

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const { token, user } = await requireUser();
  if (user.role === "employee") redirect("/tickets?mine=1");
  const { lang, display } = await getPrefs();
  const ui = dict(lang);
  const sp = await searchParams;
  const days = (PERIODS as readonly string[]).includes(sp.days ?? "") ? (sp.days as string) : "30";

  const [d, latest] = await Promise.all([
    api<Dashboard>(`/dashboard/?days=${days}`, { token }),
    api<Paginated<Ticket>>("/tickets/", { token }).catch(() => null),
  ]);
  const recent = (latest?.results ?? []).slice(0, 6);
  const statusTotal = d.by_status.reduce((sum, r) => sum + r.n, 0);
  const avg = d.avg_resolution_hours === null ? "—" : `${d.avg_resolution_hours} ${ui.hoursUnit}`;

  return (
    <>
      <div className={s.head}>
        <div>
          <div className="crumbs">{ui.dashboard}</div>
          <h1>{ui.tickets}</h1>
          <p className={s.sub}>{ui.dashSubtitle}</p>
        </div>
        <div className={s.toolbar}>
          <nav className={s.seg} aria-label={ui.periodLabel}>
            {PERIODS.map((p) => (
              <Link key={p} href={`/dashboard?days=${p}`} className={p === days ? s.on : undefined} aria-current={p === days ? "page" : undefined}>
                {p}D
              </Link>
            ))}
          </nav>
          <Link className={s.refresh} href={`/dashboard?days=${days}`}>{ui.refresh}</Link>
          <Link className="btn btn-primary" href="/tickets/new">+ {ui.newRequest}</Link>
        </div>
      </div>

      <div className={s.kpis}>
        <Link href="/tickets" className={`${s.kpi} ${s.dark}`}>
          <div className={s.v}>{d.total}</div>
          <div className={s.k}>{ui.kpiTotal}</div>
        </Link>
        <Link href="/tickets?status=open" className={s.kpi}>
          <div className={s.v}>{d.open}</div>
          <div className={s.k}>{ui.kpiOpen}</div>
        </Link>
        <Link href="/tickets" className={s.kpi}>
          <div className={`${s.v} ${(d.sla?.resolution_breached ?? 0) > 0 ? s.sevBad : ""}`}>{d.sla?.resolution_breached ?? 0}</div>
          <div className={s.k}>{ui.kpiBreached}</div>
        </Link>
        <Link href="/tickets" className={s.kpi}>
          <div className={s.v}>{d.sla?.at_risk ?? 0}</div>
          <div className={s.k}>{ui.kpiAtRisk}</div>
        </Link>
        <Link href="/tickets?status=resolved" className={s.kpi}>
          <div className={s.v}>{d.resolved}</div>
          <div className={s.k}>{ui.kpiResolved}</div>
        </Link>
        <div className={s.kpi}>
          <div className={s.v}>{avg}</div>
          <div className={s.k}>{ui.kpiAvg}</div>
        </div>
      </div>

      <div className={s.split}>
        <section className={s.panel}>
          <div className={s.panelHead}>
            <h2>{ui.latestTickets}</h2>
            <Link href="/tickets">{ui.viewAll}</Link>
          </div>
          {recent.length === 0 && <p className={s.empty}>{ui.noTickets}</p>}
          {recent.map((t) => (
            <Link key={t.number} href={`/tickets/${t.number}`} className={s.row} style={{ color: "inherit", textDecoration: "none" }}>
              <span className={s.num}>{t.number}</span>
              <BilingualText className={s.ttl} en={t.title} ar={t.title_ar} display={display} primary={t.title_ar ? lang : "en"} />
              <span style={{ justifySelf: "end" }}>
                {t.sla_resolution_status && <SlaBadge state={t.sla_resolution_status} lang={lang} />}
              </span>
            </Link>
          ))}
        </section>

        <section className={s.panel}>
          <div className={s.panelHead}>
            <h2>{ui.byStatus}</h2>
          </div>
          {d.by_status.length === 0 && <p className={s.empty}>{ui.noStatusData}</p>}
          <div className={s.bars}>
            {d.by_status.map((r) => {
              const pct = statusTotal ? Math.round((r.n / statusTotal) * 100) : 0;
              return (
                <div key={r.status} className={s.barRow}>
                  <div className={s.barLabel}>
                    <span>{ui.statusNames[r.status] ?? r.status}</span>
                    <span>{r.n} · {pct}%</span>
                  </div>
                  <div className={s.barTrack}>
                    <div className={s.barFill} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {d.sla && (
        <>
          <div className={s.panelHead} style={{ marginTop: 4 }}>
            <h2 style={{ fontSize: 16, margin: 0 }}>{ui.slaSummary}</h2>
          </div>
          <div className={s.sla} style={{ marginBottom: 16, marginTop: 8 }}>
            <div className={s.kpi}><div className={s.v}>{d.sla.response_breached}</div><div className={s.k}>{ui.slaResponseBreached}</div></div>
            <div className={s.kpi}><div className={s.v}>{d.sla.resolution_breached}</div><div className={s.k}>{ui.slaResolutionBreached}</div></div>
            <div className={s.kpi}><div className={s.v}>{d.sla.at_risk}</div><div className={s.k}>{ui.slaAtRiskCount}</div></div>
            <div className={s.kpi}><div className={s.v}>{d.sla.met_percent === null ? "—" : `${d.sla.met_percent}%`}</div><div className={s.k}>{ui.slaMetPercent}</div></div>
          </div>
        </>
      )}

      <div className={s.panelHead}>
        <h2 style={{ fontSize: 16, margin: 0 }}>{ui.quickActions}</h2>
      </div>
      <div className={s.actions} style={{ marginTop: 8, marginBottom: 16 }}>
        <Link href="/tickets/new" className={s.action}>
          <strong>+ {ui.newRequest}</strong>
          <span>{ui.quickNewDesc}</span>
          <span className={s.go} style={{ display: "block" }}>{ui.newRequest} →</span>
        </Link>
        <Link href="/approvals" className={s.action}>
          <strong>{ui.approvals} ({d.pending_approvals})</strong>
          <span>{ui.quickApprovalsDesc}</span>
          <span className={s.go} style={{ display: "block" }}>{ui.approvals} →</span>
        </Link>
        <Link href="/tasks" className={s.action}>
          <strong>{ui.myTasks} ({d.my_open_tasks})</strong>
          <span>{ui.quickTasksDesc}</span>
          <span className={s.go} style={{ display: "block" }}>{ui.myTasks} →</span>
        </Link>
      </div>
    </>
  );
}
