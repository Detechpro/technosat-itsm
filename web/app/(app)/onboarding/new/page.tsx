import type { Metadata } from "next";
import { submitOnboarding } from "@/app/actions";
import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { Flash } from "@/components/Flash";
import type { Directory } from "@/lib/types";

export const metadata: Metadata = { title: "New onboarding" };

const EMPLOYMENT = ["Full-time", "Part-time", "Contractor", "Intern"];

export default async function OnboardingPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const { token, user } = await requireUser();
  const { lang } = await getPrefs();
  const ui = dict(lang);
  if (!(user.is_global_admin || user.role === "hr_admin")) {
    return <div className="msg msg-error">{ui.onlyHr}</div>;
  }
  const sp = await searchParams;
  const approvers = await api<Directory[]>("/users/?approvers=1", { token });
  return (
    <>
      <div className="crumbs">{ui.employees}</div>
      <h1>{ui.onboardingTitle}</h1>
      <Flash error={sp.error} />
      <div className="card" style={{ maxWidth: 820 }}>
        <form action={submitOnboarding}>
          <div className="row">
            <div><label htmlFor="employee_name">{ui.fullName}</label><input id="employee_name" name="employee_name" required /></div>
            <div><label htmlFor="employee_id">{ui.employeeId}</label><input id="employee_id" name="employee_id" /></div>
          </div>
          <div className="row">
            <div><label htmlFor="company_email">{ui.companyEmail}</label><input id="company_email" name="company_email" type="email" required /></div>
            <div><label htmlFor="personal_email">{ui.personalEmail}</label><input id="personal_email" name="personal_email" type="email" /></div>
          </div>
          <div className="row">
            <div><label htmlFor="job_title">{ui.jobTitle}</label><input id="job_title" name="job_title" required /></div>
            <div><label htmlFor="joining_date">{ui.joiningDate}</label><input id="joining_date" name="joining_date" type="date" required /></div>
          </div>
          <div className="row">
            <div>
              <label htmlFor="employment_type">{ui.employmentType}</label>
              <select id="employment_type" name="employment_type" defaultValue="Full-time">
                {EMPLOYMENT.map((v) => (<option key={v} value={v}>{ui.employmentTypes[v] ?? v}</option>))}
              </select>
            </div>
            <div><label htmlFor="office_location">{ui.officeLocation}</label><input id="office_location" name="office_location" /></div>
          </div>
          <div className="row">
            <div><label htmlFor="m365_license">{ui.m365License}</label><input id="m365_license" name="m365_license" placeholder="e.g. Microsoft 365 E3" /></div>
            <div>
              <label htmlFor="approver">{ui.approvingManager}</label>
              <select id="approver" name="approver" required defaultValue="">
                <option value="" disabled>{ui.choose}</option>
                {approvers.map((a) => (<option key={a.id} value={a.id}>{a.display_name} ({a.role_label})</option>))}
              </select>
            </div>
          </div>
          <label style={{ fontWeight: 400 }}>
            <input type="checkbox" name="laptop_required" defaultChecked style={{ width: "auto", marginRight: 6 }} />
            {ui.laptopRequired}
          </label>
          <label htmlFor="software_requirements">{ui.softwareRequirements}</label>
          <textarea id="software_requirements" name="software_requirements" />
          <label htmlFor="special_permissions">{ui.specialPermissions}</label>
          <textarea id="special_permissions" name="special_permissions" />
          <label htmlFor="notes">{ui.additionalInstructions}</label>
          <textarea id="notes" name="notes" />
          <p style={{ marginTop: 16 }}>
            <button className="btn btn-primary" type="submit">{ui.submitApproval}</button>
          </p>
          <p className="help">{ui.onboardingNote}</p>
        </form>
      </div>
    </>
  );
}
