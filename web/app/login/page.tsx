import type { Metadata } from "next";
import { login } from "../actions";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  return (
    <div className="auth">
      <div className="brand-mark">IT Service Portal</div>
      <div className="card">
        <h1>Sign in</h1>
        <p className="muted" style={{ marginTop: 0 }}>Submit and track IT requests.</p>
        {sp.error && <div className="msg msg-error" role="alert">{sp.error}</div>}

        <a className="btn sso" href="/sso/microsoft">
          <svg width="16" height="16" viewBox="0 0 21 21" aria-hidden="true">
            <rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect x="11" y="1" width="9" height="9" fill="#7fba00" />
            <rect x="1" y="11" width="9" height="9" fill="#00a4ef" /><rect x="11" y="11" width="9" height="9" fill="#ffb900" />
          </svg>
          Sign in with Microsoft (administrators)
        </a>

        <div className="divider"><span>or</span></div>

        <form action={login}>
          <input type="hidden" name="next" value={sp.next ?? "/dashboard"} />
          <label htmlFor="username">Email</label>
          <input id="username" name="username" type="email" autoComplete="username" required />
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required />
          <p><button className="btn btn-primary" type="submit" style={{ width: "100%" }}>Sign in</button></p>
        </form>
        <p className="help">No account yet? Use the invitation email from your IT team. Forgot your password? Ask IT to resend your invitation.</p>
      </div>
    </div>
  );
}
