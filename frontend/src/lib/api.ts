// fm-web API client — typed fetch wrapper.
//
// All API paths start with `/api` (Vite proxies them to the FastAPI
// backend in dev; in prod they share an origin). `credentials:
// 'include'` sends the session cookie on every request — auth state
// lives server-side.

import type { components } from "../types/api";

/** API error — preserves status code + server detail for UI display. */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string, message?: string) {
    super(message ?? `${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // non-JSON body; keep statusText
    }
    throw new ApiError(res.status, String(detail));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- typed endpoint helpers ---------------------------------------

export type SessionInfo =
  components["schemas"]["SessionInfo"];
export type SignonRequest =
  components["schemas"]["SignonRequest"];
export type FileDef = components["schemas"]["FileDef"];
export type FieldDef = components["schemas"]["FieldDef"];
export type Entry = components["schemas"]["Entry"];
export type EntryPage = components["schemas"]["EntryPage"];
export type PackageDef = components["schemas"]["PackageDef"];
export type CrossRefInfo = components["schemas"]["CrossRefInfo"];

type HealthResp = { status: string; sessions: number };

export const api = {
  health: () => request<HealthResp>("/api/health"),

  // Session
  signon: (body: SignonRequest) =>
    request<SessionInfo>("/api/session/signon", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  me: () => request<SessionInfo>("/api/session/me"),
  signoff: () =>
    request<void>("/api/session/signoff", { method: "POST" }),

  // Files
  listFiles: (limit = 200) =>
    request<FileDef[]>(`/api/files?limit=${limit}`),
  getFile: (n: number) =>
    request<FileDef>(`/api/files/${n}`),
  getField: (n: number, f: number) =>
    request<FieldDef>(`/api/files/${n}/fields/${f}`),
  listCrossRefs: (n: number) =>
    request<CrossRefInfo[]>(`/api/files/${n}/xrefs`),

  // Entries
  listEntries: (
    n: number,
    { limit = 25, cursor = "" }: { limit?: number; cursor?: string } = {},
  ) => {
    const qs = new URLSearchParams({ limit: String(limit) });
    if (cursor) qs.set("cursor", cursor);
    return request<EntryPage>(`/api/files/${n}/entries?${qs}`);
  },
  getEntry: (n: number, ien: string, fields = "*") =>
    request<Entry>(
      `/api/files/${n}/entries/${ien}?fields=${encodeURIComponent(fields)}`,
    ),

  // Packages
  listPackages: (limit = 500) =>
    request<PackageDef[]>(`/api/packages?limit=${limit}`),
  getPackage: (ien: string) =>
    request<PackageDef>(`/api/packages/${ien}`),
  filesByPackage: (ien: string) =>
    request<number[]>(`/api/packages/${ien}/files`),
};
