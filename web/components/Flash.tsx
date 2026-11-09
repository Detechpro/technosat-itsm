export function Flash({ ok, error }: { ok?: string; error?: string }) {
  if (!ok && !error) return null;
  return <div className={`msg ${error ? "msg-error" : "msg-ok"}`} role={error ? "alert" : "status"}>{error ?? ok}</div>;
}
