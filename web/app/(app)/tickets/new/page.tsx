import type { Metadata } from "next";
import { createTicket } from "@/app/actions";
import { requireUser } from "@/lib/session";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { Flash } from "@/components/Flash";
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS } from "@/lib/types";

export const metadata: Metadata = { title: "New request" };

export default async function NewTicketPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  await requireUser();
  const { lang } = await getPrefs();
  const ui = dict(lang);
  const sp = await searchParams;
  return (
    <>
      <div className="crumbs">{ui.serviceDesk}</div>
      <h1>{ui.newRequest}</h1>
      <Flash error={sp.error} />
      <div className="card" style={{ maxWidth: 760 }}>
        <form action={createTicket}>
          <p className="help" style={{ marginTop: 0 }}>{ui.titleHelp}</p>
          <label htmlFor="title">{ui.titleEn}</label>
          <input id="title" name="title" minLength={5} maxLength={200} placeholder="e.g. VPN disconnects every hour" />
          <label htmlFor="title_ar">{ui.titleAr}</label>
          <input id="title_ar" name="title_ar" dir="rtl" lang="ar" maxLength={200} placeholder="مثال: انقطاع الاتصال بالشبكة الخاصة كل ساعة" />
          <label htmlFor="source_language">{ui.language}</label>
          <select id="source_language" name="source_language" defaultValue={lang}>
            <option value="en">{ui.english}</option>
            <option value="ar">{ui.arabic}</option>
          </select>
          <label htmlFor="category">{ui.category}</label>
          <select id="category" name="category" defaultValue="general">
            {CATEGORY_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          <label htmlFor="priority">{ui.priority}</label>
          <select id="priority" name="priority" defaultValue="medium">
            {PRIORITY_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          <label htmlFor="description">{ui.descriptionEn}</label>
          <textarea id="description" name="description" placeholder="What happened, what you expected, any error text" />
          <label htmlFor="description_ar">{ui.descriptionAr}</label>
          <textarea id="description_ar" name="description_ar" dir="rtl" lang="ar" placeholder="ما الذي حدث، وما الذي كنت تتوقعه، وأي نص للخطأ" />
          <label htmlFor="due_date">{ui.neededBy}</label>
          <input id="due_date" name="due_date" type="datetime-local" />
          <p style={{ marginTop: 16 }}><button className="btn btn-primary" type="submit">{ui.submitRequest}</button></p>
          <p className="help">{ui.equipmentNote}</p>
        </form>
      </div>
    </>
  );
}
