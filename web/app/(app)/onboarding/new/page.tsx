import type { Metadata } from "next";
import { submitOnboarding } from "@/app/actions";
import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";
import { Flash } from "@/components/Flash";
import type { Directory } from "@/lib/types";

export const metadata: Metadata = { title: "New onboarding" };

export default async function OnboardingPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const { token, user } = await requireUser();
  if (!(user.is_global_admin || user.role === "hr_admin")) {
    return <div className="msg msg-error">Only HR and IT administrators can submit onboarding requests.</div>;
  }
  const sp = await searchParams;
  const approvers = await api<Directory[]>("/users/?approvers=1", { token });
  return (
    <>
      <div className="crumbs">Employees</div>
      <h1>New onboarding request</h1>
      <Flash error={sp.error} />
      <div className="card" style={{ maxWidth: 820 }}>
        <form action={submitOnboarding}>
          <div className="row">
            <div><label htmlFor="employee_name">Full name</label><input id="employee_name" name="employee_name" required /></div>
            <div><label htmlFor="employee_id">Employee ID</label><input id="employee_id" name="employee_id" /></div>
          </div>
          <div className="row">
            <div><label htmlFor="company_email">Company email (required)</label><input id="company_email" name="company_email" type="email" required /></div>
            <div><label htmlFor="personal_email">Personal email</label><input id="personal_email" name="personal_email" type="email" /></div>
          </div>
          <div className="row">
            <div><label htmlFor="job_title">Job title</label><input id="job_title" name="job_title" required /></div>
            <div><label htmlFor="joining_date">Joining date</label><input id="joining_date" name="joining_date" type="date" required /></div>
          </div>
          <div className="row">
            <div>
              <label htmlFor="employment_type">Employment type</label>
              <select id="employment_type" name="employment_type" defaultValue="Full-time">
                <option>Full-time</option><option>Part-time</option><option>Contractor</option><option>Intern</option>
              </select>
            </div>
            <div><label htmlFor="office_location">Office location</label><input id="office_location" name="office_location" /></div>
          </div>
          <div className="row">
            <div><label htmlFor="m365_license">Microsoft 365 license</label><input id="m365_license" name="m365_license" placeholder="e.g. Microsoft 365 E3" /></div>
            <div>
              <label htmlFor="approver">Approving manager</label>
              <select id="approver" name="approver" required defaultValue="">
                <option value="" disabled>Choose…</option>
                {approvers.map((a) => (<option key={a.id} value={a.id}>{a.display_name} ({a.role_label})</option>))}
              </select>
            </div>
          </div>
          <label style={{ fontWeight: 400 }}>
            <input type="checkbox" name="laptop_required" defaultChecked style={{ width: "auto", marginRight: 6 }} />
            Laptop required
          </label>
          <label htmlFor="software_requirements">Software requirements</label>
          <textarea id="software_requirements" name="software_requirements" />
          <label htmlFor="special_permissions">Special permissions</label>
          <textarea id="special_permissions" name="special_permissions" />
          <label htmlFor="notes">Additional instructions</label>
          <textarea id="notes" name="notes" />
          <p style={{ marginTop: 16 }}>
            <button className="btn btn-primary" type="submit">Submit for approval</button>
          </p>
          <p className="help">No IT accounts are created until the manager approves.</p>
        </form>
      </div>
    </>
  );
}
