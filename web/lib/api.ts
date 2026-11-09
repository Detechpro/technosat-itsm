import "server-only";

/**
 * Server-side client for the Django API. The browser never talks to Django directly, so the
 * API token stays in an httpOnly cookie and is never exposed to client JavaScript.
 */
const BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type ApiInit = Omit<RequestInit, "body"> & { token?: string | null; body?: unknown };

export async function api<T>(path: string, { token, body, headers, ...init }: ApiInit = {}): Promise<T> {
  const h = new Headers(headers);
  h.set("Accept", "application/json");
  if (body !== undefined) h.set("Content-Type", "application/json");
  if (token) h.set("Authorization", `Token ${token}`);
  const res = await fetch(`${BASE}/api/v1${path}`, {
    ...init,
    headers: h,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const message =
      data?.error?.message ??
      data?.detail ??
      (data && typeof data === "object"
        ? Object.values(data).flat().map(String).join(" ")
        : res.statusText);
    throw new ApiError(res.status, message || "Request failed");
  }
  return data as T;
}
