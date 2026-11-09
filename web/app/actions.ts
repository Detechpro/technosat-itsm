"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { withFlash } from "@/lib/flash";
import { getToken } from "@/lib/session";

type Result = { ok: true } | { ok: false; message: string };

async function call(path: string, init: { method?: string; body?: unknown }): Promise<Result> {
  const token = await getToken();
  if (!token) return { ok: false, message: "Your session has expired. Please sign in again." };
  try {
    await api(path, { ...init, token, method: init.method ?? "POST" });
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return { ok: false, message: "Please sign in again." };
    return { ok: false, message: err instanceof Error ? err.message : "Something went wrong." };
  }
}

function str(form: FormData, key: string): string {
  return String(form.get(key) ?? "").trim();
}

export async function login(form: FormData) {
  const username = str(form, "username");
  const password = String(form.get("password") ?? "");
  const next = str(form, "next") || "/dashboard";
  let token: string;
  try {
    const data = await api<{ token: string }>("/auth/token/", { method: "POST", body: { username, password } });
    token = data.token;
  } catch (err) {
    const message = err instanceof ApiError && err.status === 429
      ? "Too many attempts. Please wait a minute."
      : "Username or password is incorrect.";
    redirect(`/login?error=${encodeURIComponent(message)}&next=${encodeURIComponent(next)}`);
  }
  const { cookies } = await import("next/headers");
  const { SESSION_COOKIE } = await import("@/lib/session");
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  redirect(next.startsWith("/") ? next : "/dashboard");
}

export async function logout() {
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
  const body = {
    title: str(form, "title"),
    description: str(form, "description"),
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
    redirect(withFlash("/tickets/new", "error", err instanceof Error ? err.message : "Could not create ticket."));
  }
  revalidatePath("/tickets");
  redirect(withFlash(`/tickets/${number}`, "ok", "Request submitted."));
}

export async function addComment(number: string, form: FormData) {
  const r = await call(`/tickets/${number}/comments/`, {
    body: { body: str(form, "body"), is_internal: form.get("is_internal") === "on" },
  });
  revalidatePath(`/tickets/${number}`);
  redirect(withFlash(`/tickets/${number}`, r.ok ? "ok" : "error", r.ok ? "Comment added." : r.message));
}

export async function setStatus(number: string, form: FormData) {
  const r = await call(`/tickets/${number}/status/`, { body: { status: str(form, "status") } });
  revalidatePath(`/tickets/${number}`);
  revalidatePath("/tickets");
  redirect(withFlash(`/tickets/${number}`, r.ok ? "ok" : "error", r.ok ? "Status updated." : r.message));
}

export async function reopenTicket(number: string) {
  const r = await call(`/tickets/${number}/reopen/`, { body: {} });
  revalidatePath(`/tickets/${number}`);
  redirect(withFlash(`/tickets/${number}`, r.ok ? "ok" : "error", r.ok ? "Ticket reopened." : r.message));
}

export async function decideApproval(id: number, form: FormData) {
  const decision = str(form, "decision");
  const r = await call(`/approvals/${id}/decide/`, { body: { decision, comment: str(form, "comment") } });
  revalidatePath("/approvals");
  redirect(withFlash("/approvals", r.ok ? "ok" : "error", r.ok ? `Request ${decision}.` : r.message));
}

export async function completeTask(id: number, done: boolean, back: string) {
  const r = await call(`/tasks/${id}/complete/`, { body: { done } });
  revalidatePath(back);
  redirect(withFlash(back, r.ok ? "ok" : "error", r.ok ? "Task updated." : r.message));
}

export async function submitOnboarding(form: FormData) {
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
    redirect(withFlash("/onboarding/new", "error", err instanceof Error ? err.message : "Could not submit."));
  }
  revalidatePath("/onboarding");
  redirect(withFlash(`/tickets/${number}`, "ok", "Onboarding submitted for manager approval."));
}
