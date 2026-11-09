import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { addComment, completeTask, reopenTicket, setStatus } from "@/app/actions";
import { ApiError, api } from "@/lib/api";
import { fmtDate, requireUser } from "@/lib/session";
import { StatusBadge } from "@/components/Status";
import { Flash } from "@/components/Flash";
import type { Comment, Task, Ticket } from "@/lib/types";
import { STATUS_OPTIONS } from "@/lib/types";

export const metadata: Metadata = { title: "Ticket" };

export default async function TicketDetail({ params, searchParams }: {
  params: Promise<{ number: string }>; searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { token, user } = await requireUser();
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
      <div className="crumbs"><Link href="/tickets">Tickets</Link> / {ticket.number}</div>
      <div className="topbar">
        <div>
          <h1>{ticket.title}</h1>
          <div className="badges">
            <span className="badge">{ticket.category_label}</span>
            <span className="badge">{ticket.priority_label}</span>
            <StatusBadge value={ticket.status} label={ticket.status_label} />
            {ticket.is_overdue && <StatusBadge value="overdue" label="Overdue" />}
          </div>
        </div>
      </div>
      <Flash ok={sp.ok} error={sp.error} />

      <div className="grid two" style={{ alignItems: "start" }}>
        <div>
          <div className="card">
            <h2>Description</h2>
            <p className="pre">{ticket.description || "No description provided."}</p>
          </div>

          {tasks.length > 0 && (
            <div className="card">
              <h2>Tasks</h2>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Task</th><th>Owner</th><th>Status</th><th></th></tr></thead>
                  <tbody>
                    {tasks.map((t) => (
                      <tr key={t.id}>
                        <td>{t.title}{t.result && <div className="help">{t.result}</div>}</td>
                        <td>{t.assignee ?? "Unassigned"}</td>
                        <td><StatusBadge value={t.status} label={t.status_label} /></td>
                        <td>
                          {(t.assignee === user.display_name || user.is_global_admin) && (
                            <form action={completeTask.bind(null, t.id, t.status !== "done", `/tickets/${number}`)}>
                              <button className="btn" type="submit">{t.status === "done" ? "Reopen" : "Mark done"}</button>
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
            <h2>Conversation</h2>
            <ul className="timeline">
              {comments.map((c) => (
                <li key={c.id}>
                  <strong>{c.author}</strong> <span className="muted">· {fmtDate(c.created_at)}</span>
                  {c.is_internal && <> <span className="badge b-warn">internal</span></>}
                  <div className="pre">{c.body}</div>
                </li>
              ))}
              {comments.length === 0 && <li className="muted">No comments yet.</li>}
            </ul>
            {!closed && (
              <form action={addComment.bind(null, number)} style={{ marginTop: 12 }}>
                <textarea name="body" required maxLength={5000} placeholder="Write a comment…" aria-label="Comment" />
                {staff && (
                  <label style={{ fontWeight: 400 }}>
                    <input type="checkbox" name="is_internal" style={{ width: "auto", marginRight: 6 }} />
                    Internal note (hidden from requester)
                  </label>
                )}
                <p><button className="btn btn-primary" type="submit">Add comment</button></p>
              </form>
            )}
          </div>
        </div>

        <div>
          <div className="card">
            <h2>Details</h2>
            <table>
              <tbody>
                <tr><th>Number</th><td>{ticket.number}</td></tr>
                <tr><th>Requester</th><td>{ticket.requester_name}</td></tr>
                <tr><th>Assignee</th><td>{ticket.assignee_name ?? "Unassigned"}</td></tr>
                <tr><th>Department</th><td>{ticket.department ?? "—"}</td></tr>
                <tr><th>Created</th><td>{fmtDate(ticket.created_at)}</td></tr>
                <tr><th>Due</th><td>{ticket.due_date ? fmtDate(ticket.due_date) : "—"}</td></tr>
              </tbody>
            </table>
          </div>

          {canSetStatus && (
            <div className="card">
              <h2>Update status</h2>
              <form action={setStatus.bind(null, number)} className="row">
                <select name="status" defaultValue={ticket.status} aria-label="Status">
                  {STATUS_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
                </select>
                <button className="btn btn-primary auto" type="submit">Save</button>
              </form>
            </div>
          )}

          {closed && (ticket.requester === user.username || user.is_global_admin) && (
            <div className="card">
              <form action={reopenTicket.bind(null, number)}>
                <button className="btn" type="submit" style={{ width: "100%" }}>Reopen ticket</button>
              </form>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
