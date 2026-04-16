import { useFile } from "../lib/hooks";
import { useNav } from "../lib/nav";
import type { FileDef, FieldDef } from "../lib/api";

export default function FileDetailPage({ fileNumber }: { fileNumber: number }) {
  const file = useFile(fileNumber);
  const nav = useNav();

  if (file.isLoading) return <p className="p-6">Loading file {fileNumber}...</p>;
  if (file.isError)
    return <p className="p-6 text-red-600">{file.error.message}</p>;
  if (!file.data) return <p className="p-6">File not found.</p>;

  const f: FileDef = file.data;
  const fields = Object.values(f.fields ?? {}) as FieldDef[];
  fields.sort((a, b) => a.field_number - b.field_number);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <button
        onClick={() => nav.back()}
        className="mb-4 text-sm text-blue-600 hover:underline"
      >
        &larr; Back
      </button>

      {/* Header */}
      <div className="mb-6 rounded border border-gray-300 p-4 dark:border-gray-700">
        <h1 className="mb-2 text-2xl font-bold">
          #{f.file_number} {f.label}
        </h1>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="font-medium">Global Root</dt>
          <dd className="font-mono">{f.global_root || "—"}</dd>
          <dt className="font-medium">Package</dt>
          <dd>{f.package || "—"}</dd>
          <dt className="font-medium">Field Count</dt>
          <dd>{fields.length}</dd>
        </dl>
        <div className="mt-3 flex gap-2">
          <button
            onClick={() =>
              nav.go({ page: "entries", fileNumber: f.file_number })
            }
            className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
          >
            Browse Entries
          </button>
        </div>
      </div>

      {/* Fields table */}
      <h2 className="mb-2 text-lg font-semibold">Fields</h2>
      {fields.length === 0 ? (
        <p className="text-sm text-gray-500">
          No fields loaded. This file may use shallow enumeration — click
          a field number to load full attributes.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b text-left font-semibold">
                <th className="px-2 py-1">Field #</th>
                <th className="px-2 py-1">Label</th>
                <th className="px-2 py-1">Type</th>
                <th className="px-2 py-1">Pointer</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((fd) => (
                <tr
                  key={fd.field_number}
                  onClick={() =>
                    nav.go({
                      page: "field-detail",
                      fileNumber: f.file_number,
                      fieldNumber: fd.field_number,
                    })
                  }
                  className="cursor-pointer border-b hover:bg-blue-50 dark:hover:bg-gray-800"
                >
                  <td className="px-2 py-1 font-mono">{fd.field_number}</td>
                  <td className="px-2 py-1">{fd.label}</td>
                  <td className="px-2 py-1">
                    {fd.type?.name ?? fd.type?.raw ?? "—"}
                  </td>
                  <td className="px-2 py-1 font-mono text-gray-500">
                    {fd.type?.pointer_file != null
                      ? `→ #${fd.type.pointer_file}`
                      : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
