import { useState } from "react";
import { useEntries } from "../lib/hooks";
import { useNav } from "../lib/nav";

export default function EntriesPage({
  fileNumber,
  initialCursor,
}: {
  fileNumber: number;
  initialCursor?: string;
}) {
  const nav = useNav();
  const [cursor, setCursor] = useState(initialCursor ?? "");
  const [pageSize] = useState(50);
  const entries = useEntries(fileNumber, { limit: pageSize, cursor });

  return (
    <div className="mx-auto max-w-5xl p-6">
      <button
        onClick={() => nav.go({ page: "file-detail", fileNumber })}
        className="mb-4 text-sm text-blue-600 hover:underline"
      >
        &larr; Back to file #{fileNumber}
      </button>

      <h1 className="mb-4 text-2xl font-bold">
        Entries — File #{fileNumber}
      </h1>

      {entries.isLoading ? (
        <p>Loading entries...</p>
      ) : entries.isError ? (
        <p className="text-red-600">{entries.error.message}</p>
      ) : (
        <>
          <div className="mb-2 flex items-center gap-4 text-sm text-gray-500">
            <span>{entries.data?.entries.length ?? 0} entries on this page</span>
            {cursor && (
              <button
                onClick={() => setCursor("")}
                className="text-blue-600 hover:underline"
              >
                First page
              </button>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b text-left font-semibold">
                  <th className="px-2 py-1">IEN</th>
                  <th className="px-2 py-1">Name (.01)</th>
                </tr>
              </thead>
              <tbody>
                {entries.data?.entries.map((e) => (
                  <tr
                    key={e.ien}
                    onClick={() =>
                      nav.go({
                        page: "entry-detail",
                        fileNumber,
                        ien: e.ien,
                      })
                    }
                    className="cursor-pointer border-b hover:bg-blue-50 dark:hover:bg-gray-800"
                  >
                    <td className="px-2 py-1 font-mono">{e.ien}</td>
                    <td className="px-2 py-1">
                      {e.fields?.["0.01"]?.value || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="mt-4 flex gap-4">
            {cursor && (
              <button
                onClick={() => setCursor("")}
                className="rounded border px-3 py-1 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                &laquo; First
              </button>
            )}
            {entries.data?.next_cursor && (
              <button
                onClick={() => setCursor(entries.data!.next_cursor!)}
                className="rounded border px-3 py-1 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                Next &raquo;
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
