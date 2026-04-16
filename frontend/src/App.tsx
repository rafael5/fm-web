import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMe, useSignoff } from "./lib/hooks";
import { useNav, type Route } from "./lib/nav";
import SignonPage from "./pages/SignonPage";
import FilesPage from "./pages/FilesPage";
import FileDetailPage from "./pages/FileDetailPage";
import FieldDetailPage from "./pages/FieldDetailPage";
import EntriesPage from "./pages/EntriesPage";
import EntryDetailPage from "./pages/EntryDetailPage";
import PackagesPage from "./pages/PackagesPage";
import DiagnosticsPage from "./pages/DiagnosticsPage";

const queryClient = new QueryClient();

function PageRouter({ route }: { route: Route }) {
  switch (route.page) {
    case "files":
      return <FilesPage />;
    case "file-detail":
      return <FileDetailPage fileNumber={route.fileNumber} />;
    case "field-detail":
      return (
        <FieldDetailPage
          fileNumber={route.fileNumber}
          fieldNumber={route.fieldNumber}
        />
      );
    case "entries":
      return (
        <EntriesPage
          fileNumber={route.fileNumber}
          initialCursor={route.cursor}
        />
      );
    case "entry-detail":
      return (
        <EntryDetailPage fileNumber={route.fileNumber} ien={route.ien} />
      );
    case "packages":
      return <PackagesPage />;
    case "diagnostics":
      return <DiagnosticsPage />;
  }
}

function AuthGate() {
  const me = useMe();
  const signoff = useSignoff();
  const { route, go } = useNav();

  if (me.isLoading) return null;
  if (me.isError) return <SignonPage onSuccess={() => me.refetch()} />;

  const navLink = (
    page: Route["page"],
    label: string,
    r: Route = { page } as Route,
  ) => (
    <button
      onClick={() => go(r)}
      className={
        route.page === page ||
        (page === "files" &&
          ["file-detail", "field-detail", "entries", "entry-detail"].includes(
            route.page,
          ))
          ? "font-semibold underline"
          : "text-gray-600 dark:text-gray-400"
      }
    >
      {label}
    </button>
  );

  return (
    <div className="flex h-full flex-col">
      <nav className="flex items-center gap-4 border-b border-gray-200 bg-white px-6 py-3 text-sm dark:border-gray-700 dark:bg-gray-900">
        <span className="mr-auto text-lg font-bold">fm-web</span>
        {navLink("files", "Files", { page: "files" })}
        {navLink("packages", "Packages", { page: "packages" })}
        {navLink("diagnostics", "Diagnostics", { page: "diagnostics" })}
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
        <PageRouter route={route} />
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
