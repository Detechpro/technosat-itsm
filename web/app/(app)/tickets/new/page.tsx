import type { Metadata } from "next";
import { createTicket } from "@/app/actions";
import { requireUser } from "@/lib/session";
import { Flash } from "@/components/Flash";
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS } from "@/lib/types";

export const metadata: Metadata = { title: "New request" };

export default async function NewTicketPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  await requireUser();
  const sp = await searchParams;
  return (
    <>
      <div className="crumbs">Service desk</div>
      <h1>New request</h1>
      <Flash error={sp.error} />
      <div className="card" style={{ maxWidth: 760 }}>
        <form action={createTicket}>
          <label htmlFor="title">Title</label>
          <input id="title" name="title" minLength={5} maxLength={200} required placeholder="e.g. VPN disconnects every hour" />
          <label htmlFor="category">Category</label>
          <select id="category" name="category" defaultValue="general">
            {CATEGORY_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          <label htmlFor="priority">Priority</label>
          <select id="priority" name="priority" defaultValue="medium">
            {PRIORITY_OPTIONS.map(([v, l]) => (<option key={v} value={v}>{l}</option>))}
          </select>
          <label htmlFor="description">Details</label>
          <textarea id="description" name="description" placeholder="What happened, what you expected, any error text" />
          <label htmlFor="due_date">Needed by (optional)</label>
          <input id="due_date" name="due_date" type="datetime-local" />
          <p style={{ marginTop: 16 }}><button className="btn btn-primary" type="submit">Submit request</button></p>
          <p className="help">Equipment requests go to your manager for approval first.</p>
        </form>
      </div>
    </>
  );
}
