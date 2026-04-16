import { usePackages } from "../lib/hooks";

export default function PackagesPage() {
  const packages = usePackages();

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-4 text-2xl font-bold">Packages</h1>
      {packages.isLoading ? (
        <p>Loading...</p>
      ) : packages.isError ? (
        <p className="text-red-600">{packages.error.message}</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left font-semibold">
              <th className="px-2 py-1">IEN</th>
              <th className="px-2 py-1">Name</th>
              <th className="px-2 py-1">Prefix</th>
            </tr>
          </thead>
          <tbody>
            {packages.data?.map((p) => (
              <tr key={p.ien} className="border-b hover:bg-blue-50 dark:hover:bg-gray-800">
                <td className="px-2 py-1 font-mono">{p.ien}</td>
                <td className="px-2 py-1">{p.name}</td>
                <td className="px-2 py-1 font-mono">{p.prefix || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
