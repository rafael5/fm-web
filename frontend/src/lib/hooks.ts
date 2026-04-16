// TanStack Query hooks — one per /api/* surface.
//
// Queries are keyed hierarchically (`["files", n]`, `["files", n,
// "entries", cursor]`) so invalidations stay scoped. All queries
// disable automatic refetch-on-focus — VistA doesn't churn fast
// enough to warrant it, and every refetch costs a broker round-trip.

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api, ApiError, type SessionInfo, type SignonRequest } from "./api";

const DEFAULT_STALE_MS = 60_000;

// ---- session ------------------------------------------------------

export function useMe() {
  return useQuery<SessionInfo, ApiError>({
    queryKey: ["session", "me"],
    queryFn: () => api.me(),
    retry: false,                 // 401 should propagate; don't retry
    refetchOnWindowFocus: false,
    staleTime: DEFAULT_STALE_MS,
  });
}

export function useSignon() {
  const qc = useQueryClient();
  return useMutation<SessionInfo, ApiError, SignonRequest>({
    mutationFn: (body) => api.signon(body),
    onSuccess: (data) => {
      qc.setQueryData(["session", "me"], data);
    },
  });
}

export function useSignoff() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, void>({
    mutationFn: () => api.signoff(),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ["session"] });
      qc.removeQueries({ queryKey: ["files"] });
      qc.removeQueries({ queryKey: ["packages"] });
    },
  });
}

// ---- files --------------------------------------------------------

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchOnWindowFocus: false,
    staleTime: 5_000,
  });
}

export function useFiles(limit = 200) {
  return useQuery({
    queryKey: ["files", { limit }],
    queryFn: () => api.listFiles(limit),
    refetchOnWindowFocus: false,
    staleTime: DEFAULT_STALE_MS,
  });
}

export function useFile(n: number) {
  return useQuery({
    queryKey: ["files", n],
    queryFn: () => api.getFile(n),
    enabled: Number.isFinite(n),
    refetchOnWindowFocus: false,
    staleTime: DEFAULT_STALE_MS,
  });
}

export function useEntries(
  n: number,
  opts: { limit?: number; cursor?: string } = {},
) {
  return useQuery({
    queryKey: ["files", n, "entries", opts],
    queryFn: () => api.listEntries(n, opts),
    enabled: Number.isFinite(n),
    refetchOnWindowFocus: false,
    staleTime: DEFAULT_STALE_MS,
  });
}

export function useEntry(n: number, ien: string, fields = "*") {
  return useQuery({
    queryKey: ["files", n, "entries", ien, fields],
    queryFn: () => api.getEntry(n, ien, fields),
    enabled: Number.isFinite(n) && !!ien,
    refetchOnWindowFocus: false,
    staleTime: DEFAULT_STALE_MS,
  });
}

export function usePackages() {
  return useQuery({
    queryKey: ["packages"],
    queryFn: () => api.listPackages(),
    refetchOnWindowFocus: false,
    staleTime: DEFAULT_STALE_MS,
  });
}
