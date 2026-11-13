import createClient from "openapi-fetch";
import type { paths } from "./api/schema";

const KEY = "gigbid_token";
export const getToken = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
export const setToken = (t: string | null) => { try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch { /* private mode */ } };

export const api = createClient<paths>({ baseUrl: "" });
api.use({
  onRequest({ request }) {
    const t = getToken();
    if (t) request.headers.set("Authorization", `Bearer ${t}`);
    return request;
  },
});

/** Untyped endpoints (dict responses): thin fetch with auth + readable errors. */
export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg); } }
export async function raw<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* ignore */ }
    throw new ApiError(r.status, msg);
  }
  return r.json() as Promise<T>;
}
export const enc = encodeURIComponent;
