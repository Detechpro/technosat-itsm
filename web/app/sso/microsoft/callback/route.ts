import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { api, ApiError } from "@/lib/api";
import { SESSION_COOKIE } from "@/lib/session";

const STATE_COOKIE = "itsm_sso_state";

/** Microsoft redirects here with ?code & ?state. We verify state, then exchange the code via Django. */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const base = process.env.PUBLIC_URL ?? url.origin;
  const fail = (message: string) => NextResponse.redirect(new URL(`/login?error=${encodeURIComponent(message)}`, base));

  const jar = await cookies();
  const expected = jar.get(STATE_COOKIE)?.value;
  jar.delete(STATE_COOKIE);
  if (url.searchParams.get("error")) return fail("Microsoft sign-in was cancelled.");
  const code = url.searchParams.get("code") ?? "";
  const state = url.searchParams.get("state") ?? "";
  if (!code || !expected || state !== expected) return fail("Sign-in expired or was tampered with. Please try again.");

  try {
    const { token } = await api<{ token: string }>("/auth/sso/exchange/", {
      method: "POST",
      body: { code, redirect_uri: `${base}/sso/microsoft/callback` },
    });
    jar.set(SESSION_COOKIE, token, { httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 8,
      secure: process.env.NODE_ENV === "production" });
    return NextResponse.redirect(new URL("/dashboard", base));
  } catch (err) {
    return fail(err instanceof ApiError ? err.message : "Microsoft sign-in failed.");
  }
}
