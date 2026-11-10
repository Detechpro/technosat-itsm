import type { Metadata } from "next";
import Link from "next/link";
import { completeTask } from "@/app/actions";
import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { StatusBadge } from "@/components/Status";
import { Flash } from "@/components/Flash";
import type { Paginated, Task } from "@/lib/types";

export const metadata: Metadata = { title: "My tasks" };

export default async function TasksPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const { token } = await requireUser();
  const { lang } = await getPrefs();
  const ui = dict(lang);
  const sp = await searchParams;
  const tasks = await api<Paginated<Task>>("/tasks/", { token });
  return (
    <>
      <div className="crumbs">{ui.serviceDesk}</div>
      <h1>{ui.myTasks}</h1>
      <Flash ok={sp.ok} error={sp.error} />
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead><tr><th>{ui.title}</th><th>{ui.tickets}</th><th>{ui.status}</th><th></th></tr></thead>
            <tbody>
              {tasks.results.map((t) => (
                <tr key={t.id}>
                  <td>{t.title}{t.m365_action && <div className="help">{ui.microsoftStep}</div>}</td>
                  <td><Link href={`/tickets/${t.ticket}`}>{t.ticket}</Link> {t.ticket_title}</td>
                  <td><StatusBadge value={t.status} label={ui.statusNames[t.status] ?? t.status_label} /></td>
                  <td>
                    <form action={completeTask.bind(null, t.id, t.status !== "done", "/tasks")}>
                      <button className="btn" type="submit">{t.status === "done" ? ui.reopenTask : ui.complete}</button>
                    </form>
                  </td>
                </tr>
              ))}
              {tasks.results.length === 0 && <tr><td colSpan={4} className="empty">{ui.noTasks}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
