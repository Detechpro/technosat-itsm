import type { Metadata } from "next";
import Link from "next/link";
import { api } from "@/lib/api";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/session";
import type { Dashboard } from "@/lib/types";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const { token, user } = await requireUser();
  if (user.role === "employee") redirect("/tickets?mine=1");
  const d = await api<Dashboard>("/dashboard/", { token });
  const cards = [
    { label: "Total tickets", value: d.total, href: "/tickets" },
    { label: "Open", value: d.open, href: "/tickets?status=open" },
    { label: "In progress", value: d.in_progress, href: "/tickets?status=in_progress" },
    { label: "Resolved", value: d.resolved, href: "/tickets?status=resolved" },
    { label: "Overdue", value: d.overdue, href: "/tickets" },
    { label: "Pending approvals", value: d.pending_approvals, href: "/approvals" },
    { label: "My open tasks", value: d.my_open_tasks, href: "/tasks" },
  ];
  return (
    <>
      <div className="topbar">
        <div>
          <div className="crumbs">Dashboard</div>
          <h1>Hello, {user.display_name.split(" ")[0]}</h1>
        </div>
        <Link className="btn btn-primary" href="/tickets/new">+ New request</Link>
      </div>
      <div className="grid stats" style={{ marginBottom: 16 }}>
        {cards.map((c) => (
          <Link key={c.label} href={c.href} className="card stat" style={{ display: "block", color: "inherit" }}>
            <div className="n">{c.value}</div>
            <div className="l">{c.label}</div>
          </Link>
        ))}
      </div>
      <div className="grid two">
        <div className="card">
          <h2>By category</h2>
          <table>
            <tbody>
              {d.by_category.map((r) => (<tr key={r.category}><td>{r.category.replace("_", " ")}</td><td style={{ textAlign: "right" }}>{r.n}</td></tr>))}
              {d.by_category.length === 0 && <tr><td className="empty">No tickets yet.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>By priority</h2>
          <table>
            <tbody>
              {d.by_priority.map((r) => (<tr key={r.priority}><td>{r.priority}</td><td style={{ textAlign: "right" }}>{r.n}</td></tr>))}
              {d.by_priority.length === 0 && <tr><td className="empty">No tickets yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
