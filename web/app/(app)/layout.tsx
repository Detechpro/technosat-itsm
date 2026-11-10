import Link from "next/link";
import { logout, setPrefs } from "../actions";
import { requireUser } from "@/lib/session";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { Logo } from "@/components/Logo";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { user } = await requireUser();
  const { lang, display } = await getPrefs();
  const ui = dict(lang);
  const admin = user.is_global_admin;
  const lifecycle = admin || user.role === "hr_admin";
  const approver = admin || user.role === "manager";
  const requestOnly = user.role === "employee";
  return (
    <div className="shell">
      <nav className="side" aria-label="Main">
        <div className="brand"><span className="logo-panel"><Logo lang={lang} height={44} /></span></div>
        {!requestOnly && <Link href="/dashboard">{ui.dashboard}</Link>}
        <div className="group">{requestOnly ? ui.requests : ui.serviceDesk}</div>
        <Link href="/tickets">{requestOnly ? ui.myRequests : ui.tickets}</Link>
        <Link href="/tickets/new">{ui.newRequest}</Link>
        {!requestOnly && <Link href="/tasks">{ui.myTasks}</Link>}
        {approver && <Link href="/approvals">{ui.approvals}</Link>}
        {lifecycle && (<><div className="group">{ui.employees}</div><Link href="/onboarding/new">{ui.newOnboarding}</Link></>)}
        <div className="foot">
          <div className="who">{user.display_name}<br />{user.role_label}</div>
          <form action={setPrefs} className="prefs">
            <label htmlFor="lang">{ui.language}</label>
            <select id="lang" name="lang" defaultValue={lang}>
              <option value="en">{ui.english}</option>
              <option value="ar">{ui.arabic}</option>
            </select>
            <label htmlFor="display">{ui.displayMode}</label>
            <select id="display" name="display" defaultValue={display}>
              <option value="both">{ui.both}</option>
              <option value="en">{ui.english}</option>
              <option value="ar">{ui.arabic}</option>
            </select>
            <button type="submit">{ui.save}</button>
          </form>
          <form action={logout}><button type="submit">{ui.signOut}</button></form>
        </div>
      </nav>
      <main>{children}</main>
    </div>
  );
}
