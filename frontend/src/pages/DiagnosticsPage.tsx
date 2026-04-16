import { useHealth, useMe } from "../lib/hooks";

export default function DiagnosticsPage() {
  const me = useMe();
  const health = useHealth();

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-4 text-2xl font-bold">Diagnostics</h1>

      <section className="mb-6 rounded border border-gray-300 p-4 dark:border-gray-700">
        <h2 className="mb-2 font-semibold">Session</h2>
        {me.isLoading ? (
          <p>Loading...</p>
        ) : me.isError ? (
          <p className="text-red-600">
            {me.error.isUnauthorized ? "Not signed on" : me.error.detail}
          </p>
        ) : (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="font-medium">DUZ</dt>
            <dd>{me.data?.duz}</dd>
            <dt className="font-medium">Name</dt>
            <dd>{me.data?.user_name}</dd>
            <dt className="font-medium">Site</dt>
            <dd>{me.data?.site_id}</dd>
            <dt className="font-medium">UCI</dt>
            <dd>{me.data?.uci}</dd>
            <dt className="font-medium">App Context</dt>
            <dd>{me.data?.app_context}</dd>
          </dl>
        )}
      </section>

      <section className="rounded border border-gray-300 p-4 dark:border-gray-700">
        <h2 className="mb-2 font-semibold">Server</h2>
        {health.isLoading ? (
          <p>Loading...</p>
        ) : health.isError ? (
          <p className="text-red-600">{health.error.message}</p>
        ) : (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="font-medium">Status</dt>
            <dd>{health.data?.status}</dd>
            <dt className="font-medium">Active Sessions</dt>
            <dd>{health.data?.sessions}</dd>
          </dl>
        )}
      </section>
    </div>
  );
}
