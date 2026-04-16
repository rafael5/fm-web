import { useEntry } from "../lib/hooks";
import { useNav } from "../lib/nav";

export default function EntryDetailPage({
  fileNumber,
  ien,
}: {
  fileNumber: number;
  ien: string;
}) {
  const nav = useNav();
  const entry = useEntry(fileNumber, ien);

  if (entry.isLoading)
    return <p className="p-6">Loading entry {ien}...</p>;
  if (entry.isError)
    return <p className="p-6 text-red-600">{entry.error.message}</p>;
  if (!entry.data) return <p className="p-6">Entry not found.</p>;

  const fields = Object.values(entry.data.fields ?? {});
  fields.sort((a, b) => a.field_number - b.field_number);

  return (
    <div className="mx-auto max-w-4xl p-6">
      <button
        onClick={() => nav.back()}
        className="mb-4 text-sm text-blue-600 hover:underline"
      >
        &larr; Back
      </button>

      <h1 className="mb-4 text-2xl font-bold">
        File #{fileNumber} &rsaquo; IEN {ien}
      </h1>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left font-semibold">
              <th className="px-2 py-1 w-24">Field #</th>
              <th className="px-2 py-1">Value (external)</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((fv) => (
              <tr key={fv.field_number} className="border-b">
                <td className="px-2 py-1 font-mono text-gray-500">
                  {fv.field_number}
                </td>
                <td className="px-2 py-1 break-all">
                  {fv.value || (
                    <span className="text-gray-400 italic">empty</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {fields.length === 0 && (
        <p className="mt-4 text-sm text-gray-500">
          No field values returned for this entry.
        </p>
      )}
    </div>
  );
}
