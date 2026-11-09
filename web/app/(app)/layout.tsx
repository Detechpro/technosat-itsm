import Link from "next/link";
import { logout } from "../actions";
import { requireUser } from "@/lib/session";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { user } = await requireUser();
  const admin = user.is_global_admin;
  const lifecycle = admin || user.role === "hr_admin";
  const approver = admin || user.role === "manager";
  const requestOnly = user.role === "employee";
  return (
    <div className="shell">
      <nav className="side" aria-label="Main">
        <div className="brand">IT Service Portal</div>
        {!requestOnly && <Link href="/dashboard">Dashboard</Link>}
        <div className="group">{requestOnly ? "Requests" : "Service desk"}</div>
        <Link href="/tickets">{requestOnly ? "My requests" : "Tickets"}</Link>
        <Link href="/tickets/new">New request</Link>
        {!requestOnly && <Link href="/tasks">My tasks</Link>}
        {approver && <Link href="/approvals">Approvals</Link>}
        {lifecycle && (<><div className="group">Employees</div><Link href="/onboarding/new">New onboarding</Link></>)}
        <div className="foot">
          {user.display_name}<br />{user.role_label}
          <form action={logout}><button type="submit">Sign out</button></form>
        </div>
      </nav>
      <main>{children}</main>
    </div>
  );
}
