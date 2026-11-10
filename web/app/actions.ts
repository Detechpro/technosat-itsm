"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { withFlash } from "@/lib/flash";
import { getToken } from "@/lib/session";
import { cookies, headers } from "next/headers";
import { DISPLAY_COOKIE, LANG_COOKIE, isDisplay, isLang, t as dict } from "@/lib/i18n";
import { getPrefs } from "@/lib/prefs";

type Result = { ok: true } | { ok: false; message: string };

async function call(path: string, init: { method?: string; body?: unknown }): Promise<Result> {
  const token = await getToken();
  const ui = dict((await getPrefs()).lang);
  if (!token) return { ok: false, message: ui.msgExpired };
  try {
    await api(path, { ...init, token, method: init.method ?? "POST" });
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return { ok: false, message: ui.msgSignIn };
    return { ok: false, message: err instanceof Error ? err.message : ui.msgGeneric };
  }
}

function str(form: FormData, key: string): string {
  return String(form.get(key) ?? "").trim();
}

/** Only same-site relative paths may be used after sign-in. */
function safeNext(v: string): string {
  return v.startsWith("/") && !v.startsWith("//") ? v : "/dashboard";
}

/** Step 1: email a one-time code. The answer is the same whether or not the email has an account. */
export async function requestCode(form: FormData) {
  const ui = dict((await getPrefs()).lang);
  const email = str(form, "email").toLowerCase();
  const next = safeNext(str(form, "next"));
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    redirect(`/login?error=${encodeURIComponent(ui.errEmail)}&next=${encodeURIComponent(next)}`);
  }
  try {
    await api("/auth/otp/request/", { method: "POST", body: { email } });
  } catch (err) {
    const message = err instanceof ApiError && err.status === 429 ? ui.errThrottle : ui.errGeneric;
    redirect(`/login?error=${encodeURIComponent(message)}&next=${encodeURIComponent(next)}`);
  }
  const { cookies } = await import("next/headers");
  const { OTP_COOKIE } = await import("@/lib/session");
  (await cookies()).set(OTP_COOKIE, email, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 15,
  });
  redirect(`/login?step=code&next=${encodeURIComponent(next)}`);
}

/** Step 2: exchange the emailed code for a session. */
export async function verifyCode(form: FormData) {
  const ui = dict((await getPrefs()).lang);
  const { cookies } = await import("next/headers");
  const { OTP_COOKIE, SESSION_COOKIE } = await import("@/lib/session");
  const store = await cookies();
  const email = store.get(OTP_COOKIE)?.value ?? "";
  const next = safeNext(str(form, "next"));
  const code = str(form, "code").replace(/\s/g, "");
  if (!email) redirect("/login");
  if (!/^\d{6}$/.test(code)) {
    redirect(`/login?step=code&error=${encodeURIComponent(ui.errCode)}&next=${encodeURIComponent(next)}`);
  }
  let token: string;
  try {
    const data = await api<{ token: string }>("/auth/otp/verify/", { method: "POST", body: { email, code } });
    token = data.token;
  } catch (err) {
    const message = err instanceof ApiError && err.status === 429 ? ui.errThrottle : ui.errInvalidCode;
    redirect(`/login?step=code&error=${encodeURIComponent(message)}&next=${encodeURIComponent(next)}`);
  }
  store.set(SESSION_COOKIE, token, {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 60 * 8,
  });
  store.delete(OTP_COOKIE);
  redirect(next);
}

/** Go back to the email step. */
export async function cancelCode() {
  const { cookies } = await import("next/headers");
  const { OTP_COOKIE } = await import("@/lib/session");
  (await cookies()).delete(OTP_COOKIE);
  redirect("/login");
}

export async function logout() {
  const ui = dict((await getPrefs()).lang);
  const token = await getToken();
  if (token) {
    await api("/auth/logout/", { method: "POST", token }).catch(() => undefined);
  }
  const { cookies } = await import("next/headers");
  const { SESSION_COOKIE } = await import("@/lib/session");
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/login");
}

export async function createTicket(form: FormData) {
  const ui = dict((await getPrefs()).lang);
  const body = {
    title: str(form, "title"),
    title_ar: str(form, "title_ar"),
    description: str(form, "description"),
    description_ar: str(form, "description_ar"),
    source_language: str(form, "source_language") === "ar" ? "ar" : "en",
    category: str(form, "category") || "general",
    priority: str(form, "priority") || "medium",
    due_date: str(form, "due_date") ? new Date(str(form, "due_date")).toISOString() : null,
  };
  const token = await getToken();
  if (!token) redirect("/login");
  let number: string;
  try {
    const created = await api<{ number: string }>("/tickets/", { method: "POST", token, body });
    number = created.number;
  } catch (err) {
    redirect(withFlash("/tickets/new", "error", err instanceof Error ? err.message : ui.msgCreateFailed));
  }
  revalidatePath("/tickets");
  redirect(withFlash(`/tickets/${number}`, "ok", ui.msgCreated));
}

export async function addComment(number: string, form: FormData) {
  const ui = dict((await getPrefs()).lang);
  const r = await call(`/tickets/${number}/comments/`, {
    body: { body: str(form, "body"), is_internal: form.get("is_internal") === "on" },
  });
  revalidatePath(`/tickets/${number}`);
  redirect(withFlash(`/tickets/${number}`, r.ok ? "ok" : "error", r.ok ? ui.msgComment : r.message));
}

export async function setStatus(number: string, form: FormData) {
  const ui = dict((await getPrefs()).lang);
  const r = await call(`/tickets/${number}/status/`, { body: { status: str(form, "status") } });
  revalidatePath(`/tickets/${number}`);
  revalidatePath("/tickets");
  redirect(withFlash(`/tickets/${number}`, r.ok ? "ok" : "error", r.ok ? ui.msgStatus : r.message));
}

export async function reopenTicket(number: string) {
  const ui = dict((await getPrefs()).lang);
  const r = await call(`/tickets/${number}/reopen/`, { body: {} });
  revalidatePath(`/tickets/${number}`);
  redirect(withFlash(`/tickets/${number}`, r.ok ? "ok" : "error", r.ok ? ui.msgReopened : r.message));
}

export async function decideApproval(id: number, form: FormData) {
  const ui = dict((await getPrefs()).lang);
  const decision = str(form, "decision");
  const r = await call(`/approvals/${id}/decide/`, { body: { decision, comment: str(form, "comment") } });
  revalidatePath("/approvals");
  redirect(withFlash("/approvals", r.ok ? "ok" : "error", r.ok ? (decision === "approved" ? ui.msgApproved : ui.msgRejected) : r.message));
}

export async function completeTask(id: number, done: boolean, back: string) {
  const ui = dict((await getPrefs()).lang);
  const r = await call(`/tasks/${id}/complete/`, { body: { done } });
  revalidatePath(back);
  redirect(withFlash(back, r.ok ? "ok" : "error", r.ok ? ui.msgTask : r.message));
}

export async function submitOnboarding(form: FormData) {
  const ui = dict((await getPrefs()).lang);
  const body = {
    employee_name: str(form, "employee_name"),
    employee_id: str(form, "employee_id"),
    company_email: str(form, "company_email"),
    personal_email: str(form, "personal_email"),
    job_title: str(form, "job_title"),
    joining_date: str(form, "joining_date"),
    employment_type: str(form, "employment_type") || "Full-time",
    office_location: str(form, "office_location"),
    m365_license: str(form, "m365_license"),
    laptop_required: form.get("laptop_required") === "on",
    software_requirements: str(form, "software_requirements"),
    special_permissions: str(form, "special_permissions"),
    notes: str(form, "notes"),
    approver: Number(str(form, "approver")),
  };
  const token = await getToken();
  if (!token) redirect("/login");
  let number: string;
  try {
    const created = await api<{ number: string }>("/lifecycle/onboarding/", { method: "POST", token, body });
    number = created.number;
  } catch (err) {
    redirect(withFlash("/onboarding/new", "error", err instanceof Error ? err.message : ui.msgOnboardFailed));
  }
  revalidatePath("/onboarding");
  redirect(withFlash(`/tickets/${number}`, "ok", ui.msgOnboarded));
}

/** Saves the UI language and display mode in cookies, and the language to the account when signed in. */
export async function setPrefs(form: FormData) {
  const ui = dict((await getPrefs()).lang);
  const lang = String(form.get("lang") ?? "");
  const display = String(form.get("display") ?? "");
  let back = "/dashboard";
  const ref = (await headers()).get("referer");
  if (ref) {
    try { back = new URL(ref).pathname; } catch { /* keep default */ }
  }
  const store = await cookies();
  const opts = { path: "/", maxAge: 60 * 60 * 24 * 365, sameSite: "lax" as const };
  if (isLang(lang)) store.set(LANG_COOKIE, lang, opts);
  if (isDisplay(display)) store.set(DISPLAY_COOKIE, display, opts);
  if (isLang(lang) && (await getToken())) {
    await call("/auth/me/", { method: "PATCH", body: { preferred_language: lang } });
  }
  revalidatePath("/", "layout");
  redirect(back);
}
