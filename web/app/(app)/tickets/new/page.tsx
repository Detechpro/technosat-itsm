import type { Metadata } from "next";
import { createTicket } from "@/app/actions";
import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { Flash } from "@/components/Flash";
import { LanguageFields } from "@/components/LanguageFields";
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS } from "@/lib/types";

export const metadata: Metadata = { title: "New request" };

/** Roles that can take ownership of a ticket. */
const ASSIGNABLE_ROLES = ["super_admin", "it_admin", "technician"];

export default async function NewTicketPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const { token, user } = await requireUser();
  const { lang } = await getPrefs();
  const ui = dict(lang);
  const sp = await searchParams;
  // Only administrators can assign tickets, and only they can read the staff directory.
  const staff = user.is_global_admin
    ? (await api<{ id: number; display_name: string; role: string }[]>("/users/", { token }).catch(() => []))
        .filter((u) => ASSIGNABLE_ROLES.includes(u.role))
    : [];
  return (
    <>
      <div className="crumbs">{ui.serviceDesk}</div>
      <h1>{ui.newRequest}</h1>
      <Flash error={sp.error} />
      <div className="card" style={{ maxWidth: 760 }}>
        <form action={createTicket}>
          <p className="help" style={{ marginTop: 0 }}>{ui.titleHelp}</p>
          <LanguageFields
            defaultLang={lang}
            labels={{
              language: ui.language,
              english: ui.english,
              arabic: ui.arabic,
              both: ui.bothLanguages,
              titleEn: ui.titleEn,
              titleAr: ui.titleAr,
              descriptionEn: ui.descriptionEn,
              descriptionAr: ui.descriptionAr,
            }}
            placeholders={{
              titleEn: "e.g. VPN disconnects every hour",
              titleAr: "مثال: انقطاع الاتصال بالشبكة الخاصة كل ساعة",
              descEn: "What happened, what you expected, any error text",
              descAr: "ما الذي حدث، وما الذي كنت تتوقعه، وأي نص للخطأ",
            }}
          />
          <label htmlFor="category">{ui.category}</label>
          <select id="category" name="category" defaultValue="general">
            {CATEGORY_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          <label htmlFor="priority">{ui.priority}</label>
          <select id="priority" name="priority" defaultValue="medium">
            {PRIORITY_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          {staff.length > 0 && (
            <>
              <label htmlFor="assignee">{ui.assignee}</label>
              <select id="assignee" name="assignee" defaultValue="">
                <option value="">{ui.unassigned}</option>
                {staff.map((s) => (<option key={s.id} value={s.id}>{s.display_name}</option>))}
              </select>
            </>
          )}
          <label htmlFor="due_date">{ui.neededBy}</label>
          <input id="due_date" name="due_date" type="datetime-local" />
          <p style={{ marginTop: 16 }}><button className="btn btn-primary" type="submit">{ui.submitRequest}</button></p>
          <p className="help">{ui.equipmentNote}</p>
        </form>
      </div>
    </>
  );
}
