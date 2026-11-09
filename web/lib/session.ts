import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api, ApiError } from "./api";
import type { User } from "./types";

export const SESSION_COOKIE = "itsm_session";

export async function getToken(): Promise<string | null> {
  return (await cookies()).get(SESSION_COOKIE)?.value ?? null;
}

/** Returns the signed-in user or redirects to /login. Call from every protected server component. */
export async function requireUser(): Promise<{ token: string; user: User }> {
  const token = await getToken();
  if (!token) redirect("/login");
  try {
    const user = await api<User>("/auth/me/", { token });
    return { token, user };
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) redirect("/login");
    throw err;
  }
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
