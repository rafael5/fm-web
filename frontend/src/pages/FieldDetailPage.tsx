import { useQuery } from "@tanstack/react-query";
import { api, type FieldDef } from "../lib/api";
import { useNav } from "../lib/nav";

export default function FieldDetailPage({
  fileNumber,
  fieldNumber,
}: {
  fileNumber: number;
  fieldNumber: number;
}) {
  const nav = useNav();
  const field = useQuery({
    queryKey: ["files", fileNumber, "fields", fieldNumber],
    queryFn: () => api.getField(fileNumber, fieldNumber),
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  if (field.isLoading)
    return <p className="p-6">Loading field {fieldNumber}...</p>;
  if (field.isError)
    return <p className="p-6 text-red-600">{field.error?.message}</p>;
  if (!field.data) return <p className="p-6">Field not found.</p>;

  const fd: FieldDef = field.data;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <button
        onClick={() => nav.back()}
        className="mb-4 text-sm text-blue-600 hover:underline"
      >
        &larr; Back to file
      </button>

      <h1 className="mb-4 text-2xl font-bold">
        #{fileNumber} &rsaquo; {fd.label} ({fd.field_number})
      </h1>

      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="font-medium">Field Number</dt>
        <dd className="font-mono">{fd.field_number}</dd>

        <dt className="font-medium">Label</dt>
        <dd>{fd.label}</dd>

        <dt className="font-medium">Type (raw)</dt>
        <dd className="font-mono">{fd.type?.raw || "—"}</dd>

        <dt className="font-medium">Type (decoded)</dt>
        <dd>
          {fd.type?.name || "UNKNOWN"}
          {fd.type?.is_required && (
            <span className="ml-2 rounded bg-yellow-100 px-1 text-xs text-yellow-800">
              required
            </span>
          )}
          {fd.type?.is_multiple && (
            <span className="ml-2 rounded bg-purple-100 px-1 text-xs text-purple-800">
              multiple
            </span>
          )}
        </dd>

        {fd.type?.pointer_file != null && (
          <>
            <dt className="font-medium">Points To</dt>
            <dd>
              <button
                onClick={() =>
                  nav.go({
                    page: "file-detail",
                    fileNumber: fd.type!.pointer_file!,
                  })
                }
                className="text-blue-600 hover:underline"
              >
                File #{fd.type.pointer_file}
              </button>
            </dd>
          </>
        )}

        <dt className="font-medium">Storage</dt>
        <dd className="font-mono">{fd.storage || "—"}</dd>

        <dt className="font-medium">Title</dt>
        <dd>{fd.title || "—"}</dd>

        {fd.help_prompt && (
          <>
            <dt className="font-medium">Help Prompt</dt>
            <dd>{fd.help_prompt}</dd>
          </>
        )}

        {fd.input_transform && (
          <>
            <dt className="font-medium">Input Transform</dt>
            <dd className="font-mono text-xs">{fd.input_transform}</dd>
          </>
        )}

        {Object.keys(fd.set_values ?? {}).length > 0 && (
          <>
            <dt className="font-medium">Set Values</dt>
            <dd>
              <table className="text-xs">
                <tbody>
                  {Object.entries(fd.set_values!).map(([code, label]) => (
                    <tr key={code}>
                      <td className="pr-2 font-mono">{code}</td>
                      <td>{label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}
