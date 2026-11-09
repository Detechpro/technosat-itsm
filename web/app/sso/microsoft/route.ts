import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { api, ApiError } from "@/lib/api";

const STATE_COOKIE = "itsm_sso_state";

/** Starts Microsoft Entra sign-in: asks Django for the authorization URL and stores the state. */
export async function GET(req: Request) {
  const base = process.env.PUBLIC_URL ?? new URL(req.url).origin;
  try {
    const { auth_url, state } = await api<{ auth_url: string; state: string }>("/auth/sso/start/", {
      method: "POST",
      body: { redirect_uri: `${base}/sso/microsoft/callback` },
    });
    (await cookies()).set(STATE_COOKIE, state, { httpOnly: true, sameSite: "lax", path: "/", maxAge: 600,
      secure: process.env.NODE_ENV === "production" });
    return NextResponse.redirect(auth_url);
  } catch (err) {
    const message = err instanceof ApiError ? err.message : "Microsoft sign-in is unavailable right now.";
    return NextResponse.redirect(new URL(`/login?error=${encodeURIComponent(message)}`, base));
  }
}
