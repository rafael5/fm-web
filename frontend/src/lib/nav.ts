// Simple navigation state — replaces a full router for v1.
// Zustand store so any component can navigate without prop drilling.

import { create } from "zustand";

export type Route =
  | { page: "files" }
  | { page: "file-detail"; fileNumber: number }
  | { page: "field-detail"; fileNumber: number; fieldNumber: number }
  | { page: "entries"; fileNumber: number; cursor?: string }
  | { page: "entry-detail"; fileNumber: number; ien: string }
  | { page: "packages" }
  | { page: "diagnostics" };

interface NavState {
  route: Route;
  history: Route[];
  go: (r: Route) => void;
  back: () => void;
}

export const useNav = create<NavState>((set) => ({
  route: { page: "files" },
  history: [],
  go: (r) =>
    set((s) => ({ route: r, history: [...s.history, s.route] })),
  back: () =>
    set((s) => {
      const prev = s.history[s.history.length - 1];
      return prev
        ? { route: prev, history: s.history.slice(0, -1) }
        : s;
    }),
}));
