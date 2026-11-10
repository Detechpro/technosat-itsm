import type { Metadata } from "next";
import { cancelCode, requestCode, verifyCode } from "../actions";
import { getPrefs } from "@/lib/prefs";
import { t as dict } from "@/lib/i18n";
import { OTP_COOKIE } from "@/lib/session";
import { Logo } from "@/components/Logo";
import { cookies } from "next/headers";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const { lang } = await getPrefs();
  const ui = dict(lang);
  const pendingEmail = (await cookies()).get(OTP_COOKIE)?.value;
  const codeStep = sp.step === "code" && Boolean(pendingEmail);
  const next = sp.next ?? "/dashboard";
  return (
    <div className="auth">
      <div className="brand-mark"><Logo lang={lang} height={46} /></div>
      <div className="card">
        <h1>{ui.signIn}</h1>
        <p className="muted" style={{ marginTop: 0 }}>{codeStep ? ui.codeSentTo : ui.signInHelp}</p>
        {sp.error && <div className="msg msg-error" role="alert">{sp.error}</div>}

        {codeStep ? (
          <>
            <form action={verifyCode}>
              <input type="hidden" name="next" value={next} />
              <label htmlFor="code">{ui.email}: <strong dir="ltr">{pendingEmail}</strong></label>
              <input id="code" name="code" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} required dir="ltr" style={{ letterSpacing: ".3em", textAlign: "center", fontSize: 20 }} />
              <p><button className="btn btn-primary" type="submit" style={{ width: "100%" }}>{ui.signInWithCode}</button></p>
            </form>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <form action={requestCode}>
                <input type="hidden" name="email" value={pendingEmail} />
                <input type="hidden" name="next" value={next} />
                <button className="btn auto" type="submit">{ui.resendCode}</button>
              </form>
              <form action={cancelCode}>
                <button className="btn auto" type="submit">{ui.useAnother}</button>
              </form>
            </div>
          </>
        ) : (
          <>
            <a className="btn sso" href="/sso/microsoft">
              <svg width="16" height="16" viewBox="0 0 21 21" aria-hidden="true">
                <rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                <rect x="1" y="11" width="9" height="9" fill="#00a4ef" /><rect x="11" y="11" width="9" height="9" fill="#ffb900" />
              </svg>
              {ui.signInMicrosoft}
            </a>

            <div className="divider"><span>{ui.or}</span></div>

            <form action={requestCode}>
              <input type="hidden" name="next" value={next} />
              <label htmlFor="email">{ui.email}</label>
              <input id="email" name="email" type="email" autoComplete="email" required dir="ltr" />
              <p><button className="btn btn-primary" type="submit" style={{ width: "100%" }}>{ui.sendCode}</button></p>
            </form>
          </>
        )}
        <p className="help">{ui.noAccount}</p>
      </div>
    </div>
  );
}
