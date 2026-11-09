/** Server actions report success or failure by redirecting with ?ok= or ?error= (no client JS needed). */
export function withFlash(path: string, kind: "ok" | "error", message: string): string {
  const url = new URL(path, "http://local");
  url.searchParams.delete("ok");
  url.searchParams.delete("error");
  url.searchParams.set(kind, message.slice(0, 200));
  return `${url.pathname}${url.search}`;
}
