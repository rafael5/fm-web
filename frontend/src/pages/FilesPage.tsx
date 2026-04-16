import { useFiles } from "../lib/hooks";

export default function FilesPage() {
  const files = useFiles();

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-4 text-2xl font-bold">FileMan Files</h1>
      {files.isLoading ? (
        <p>Loading file list...</p>
      ) : files.isError ? (
        <p className="text-red-600">{files.error.message}</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left font-semibold">
              <th className="px-2 py-1">File #</th>
              <th className="px-2 py-1">Label</th>
            </tr>
          </thead>
          <tbody>
            {files.data?.map((f) => (
              <tr
                key={f.file_number}
                className="border-b hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <td className="px-2 py-1 font-mono">
                  {f.file_number}
                </td>
                <td className="px-2 py-1">{f.label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
