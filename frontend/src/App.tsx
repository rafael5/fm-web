import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMe, useSignoff } from "./lib/hooks";
import SignonPage from "./pages/SignonPage";
import FilesPage from "./pages/FilesPage";
import DiagnosticsPage from "./pages/DiagnosticsPage";

const queryClient = new QueryClient();

type Page = "files" | "diagnostics";

function AuthGate() {
  const me = useMe();
  const signoff = useSignoff();
  const [page, setPage] = useState<Page>("files");

  if (me.isLoading) return null;

  if (me.isError) {
    return <SignonPage onSuccess={() => me.refetch()} />;
  }

  return (
    <div className="flex h-full flex-col">
      <nav className="flex items-center gap-4 border-b border-gray-200 bg-white px-6 py-3 text-sm dark:border-gray-700 dark:bg-gray-900">
        <span className="mr-auto text-lg font-bold">fm-web</span>
        <button
          onClick={() => setPage("files")}
          className={
            page === "files"
              ? "font-semibold underline"
              : "text-gray-600 dark:text-gray-400"
          }
        >
          Files
        </button>
        <button
          onClick={() => setPage("diagnostics")}
          className={
            page === "diagnostics"
              ? "font-semibold underline"
              : "text-gray-600 dark:text-gray-400"
          }
        >
          Diagnostics
        </button>
        <span className="text-gray-500">|</span>
        <span className="text-xs text-gray-500">
          {me.data?.user_name || me.data?.duz}
        </span>
        <button
          onClick={() =>
            signoff.mutate(undefined, { onSuccess: () => me.refetch() })
          }
          className="text-red-600 hover:underline"
        >
          Sign Off
        </button>
      </nav>
      <main className="flex-1 overflow-y-auto">
        {page === "files" && <FilesPage />}
        {page === "diagnostics" && <DiagnosticsPage />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
    </QueryClientProvider>
  );
}
