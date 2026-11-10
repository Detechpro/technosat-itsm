import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { addComment, completeTask, reopenTicket, setStatus } from "@/app/actions";
import { ApiError, api } from "@/lib/api";
import { fmtDate, requireUser } from "@/lib/session";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { BilingualText } from "@/components/BilingualText";
import { SlaBadge } from "@/components/SlaBadge";
import { StatusBadge } from "@/components/Status";
import { Flash } from "@/components/Flash";
import type { Comment, Task, Ticket } from "@/lib/types";
import { STATUS_OPTIONS } from "@/lib/types";

export const metadata: Metadata = { title: "Ticket" };

export default async function TicketDetail({ params, searchParams }: {
  params: Promise<{ number: string }>; searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { token, user } = await requireUser();
  const { lang, display } = await getPrefs();
  const ui = dict(lang);
  const { number } = await params;
  const sp = await searchParams;
  let ticket: Ticket;
  try {
    ticket = await api<Ticket>(`/tickets/${number}/`, { token });
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 403)) notFound();
    throw err;
  }
  const [comments, tasks] = await Promise.all([
    api<Comment[]>(`/tickets/${number}/comments/`, { token }),
    api<{ results: Task[] }>("/tasks/?mine=0", { token }).then((r) => r.results.filter((t) => t.ticket === number)),
  ]);
  const staff = user.is_global_admin || user.role === "technician" || user.role === "asset_manager";
  const canSetStatus = user.is_global_admin || (user.role === "technician" && ticket.assignee === user.username);
  const closed = ticket.status === "resolved" || ticket.status === "closed";

  return (
    <>
      <div className="crumbs"><Link href="/tickets">{ui.tickets}</Link> / {ticket.number}</div>
      <div className="topbar">
        <div>
          <BilingualText as="h1" en={ticket.title} ar={ticket.title_ar} display={display} primary={ticket.source_language ?? "en"} />
          <div className="badges">
            <span className="badge">{lang === "ar" ? ticket.category_label_ar ?? ticket.category_label : ticket.category_label}</span>
            <span className="badge">{lang === "ar" ? ticket.priority_label_ar ?? ticket.priority_label : ticket.priority_label}</span>
            <StatusBadge value={ticket.status} label={ui.statusNames[ticket.status] ?? ticket.status_label} />
            {ticket.is_overdue && <StatusBadge value="overdue" label={ui.overdue} />}
          </div>
        </div>
      </div>
      <Flash ok={sp.ok} error={sp.error} />

      <div className="grid two" style={{ alignItems: "start" }}>
        <div>
          <div className="card">
            <h2>{ui.description}</h2>
            <BilingualText as="div" className="pre" en={ticket.description} ar={ticket.description_ar} display={display} primary={ticket.source_language ?? "en"} />
          </div>

          {tasks.length > 0 && (
            <div className="card">
              <h2>{ui.tasksHeading}</h2>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>{ui.task}</th><th>{ui.owner}</th><th>{ui.status}</th><th></th></tr></thead>
                  <tbody>
                    {tasks.map((t) => (
                      <tr key={t.id}>
                        <td>{t.title}{t.result && <div className="help">{t.result}</div>}</td>
                        <td>{t.assignee ?? ui.unassigned}</td>
                        <td><StatusBadge value={t.status} label={ui.statusNames[t.status] ?? t.status_label} /></td>
                        <td>
                          {(t.assignee === user.display_name || user.is_global_admin) && (
                            <form action={completeTask.bind(null, t.id, t.status !== "done", `/tickets/${number}`)}>
                              <button className="btn" type="submit">{t.status === "done" ? ui.reopenTask : ui.markDone}</button>
                            </form>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card">
            <h2>{ui.conversation}</h2>
            <ul className="timeline">
              {comments.map((c) => (
                <li key={c.id}>
                  <strong>{c.author}</strong> <span className="muted">· {fmtDate(c.created_at)}</span>
                  {c.is_internal && <> <span className="badge b-warn">{ui.internal}</span></>}
                  <div className="pre">{c.body}</div>
                </li>
              ))}
              {comments.length === 0 && <li className="muted">{ui.noComments}</li>}
            </ul>
            {!closed && (
              <form action={addComment.bind(null, number)} style={{ marginTop: 12 }}>
                <textarea name="body" required maxLength={5000} placeholder={ui.writeComment} aria-label={ui.comment} />
                {staff && (
                  <label style={{ fontWeight: 400 }}>
                    <input type="checkbox" name="is_internal" style={{ width: "auto", marginRight: 6 }} />
                    {ui.internalNote}
                  </label>
                )}
                <p><button className="btn btn-primary" type="submit">{ui.addComment}</button></p>
              </form>
            )}
          </div>
        </div>

        <div>
          <div className="card">
            <h2>{ui.details}</h2>
            <table>
              <tbody>
                <tr><th>{ui.number}</th><td>{ticket.number}</td></tr>
                <tr><th>{ui.requester}</th><td>{ticket.requester_name}</td></tr>
                <tr><th>{ui.assignee}</th><td>{ticket.assignee_name ?? ui.unassigned}</td></tr>
                <tr><th>{ui.department}</th><td>{ticket.department ?? "—"}</td></tr>
                <tr><th>{ui.created}</th><td>{fmtDate(ticket.created_at)}</td></tr>
                <tr><th>{ui.due}</th><td>{ticket.due_date ? fmtDate(ticket.due_date) : "—"}</td></tr>
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>{ui.slaTitle}</h2>
            <table>
              <tbody>
                <tr><th>{ui.slaResponse}</th><td>{ticket.sla_response_due ? fmtDate(ticket.sla_response_due) : "—"} <SlaBadge state={ticket.sla_response_status} lang={lang} /></td></tr>
                <tr><th>{ui.slaResolution}</th><td>{ticket.sla_resolution_due ? fmtDate(ticket.sla_resolution_due) : "—"} <SlaBadge state={ticket.sla_resolution_status} lang={lang} /></td></tr>
              </tbody>
            </table>
            {ticket.sla_at_risk && <p className="help" style={{ color: "#a1281d" }}>{ui.slaAtRisk}</p>}
            <p className="help">{ui.slaNote}</p>
          </div>

          {canSetStatus && (
            <div className="card">
              <h2>{ui.updateStatus}</h2>
              <form action={setStatus.bind(null, number)} className="row">
                <select name="status" defaultValue={ticket.status} aria-label={ui.status}>
                  {STATUS_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{ui.statusNames[v] ?? l}</option>))}
                </select>
                <button className="btn btn-primary auto" type="submit">{ui.save}</button>
              </form>
            </div>
          )}

          {closed && (ticket.requester === user.username || user.is_global_admin) && (
            <div className="card">
              <form action={reopenTicket.bind(null, number)}>
                <button className="btn" type="submit" style={{ width: "100%" }}>{ui.reopen}</button>
              </form>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
