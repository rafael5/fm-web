import { useMemo, useState } from "react";
import { useFiles } from "../lib/hooks";
import { useNav } from "../lib/nav";

export default function FilesPage() {
  const files = useFiles(5000);
  const nav = useNav();
  const [search, setSearch] = useState("");
  const [sortCol, setSortCol] = useState<"number" | "label">("number");
  const [sortAsc, setSortAsc] = useState(true);

  const filtered = useMemo(() => {
    if (!files.data) return [];
    const q = search.toLowerCase();
    let rows = files.data.filter(
      (f) =>
        !q ||
        f.label.toLowerCase().includes(q) ||
        String(f.file_number).includes(q),
    );
    rows.sort((a, b) => {
      const cmp =
        sortCol === "number"
          ? a.file_number - b.file_number
          : a.label.localeCompare(b.label);
      return sortAsc ? cmp : -cmp;
    });
    return rows;
  }, [files.data, search, sortCol, sortAsc]);

  function toggleSort(col: "number" | "label") {
    if (sortCol === col) setSortAsc(!sortAsc);
    else {
      setSortCol(col);
      setSortAsc(true);
    }
  }

  const arrow = (col: string) =>
    sortCol === col ? (sortAsc ? " \u25b2" : " \u25bc") : "";

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-4 flex items-center gap-4">
        <h1 className="text-2xl font-bold">FileMan Files</h1>
        <span className="text-sm text-gray-500">
          {files.data ? `${filtered.length} / ${files.data.length}` : ""}
        </span>
      </div>

      <input
        type="text"
        placeholder="Search by file # or name..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
      />

      {files.isLoading ? (
        <p>Loading...</p>
      ) : files.isError ? (
        <p className="text-red-600">{files.error.message}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b text-left font-semibold">
                <th
                  className="cursor-pointer px-2 py-1"
                  onClick={() => toggleSort("number")}
                >
                  File #{arrow("number")}
                </th>
                <th
                  className="cursor-pointer px-2 py-1"
                  onClick={() => toggleSort("label")}
                >
                  Label{arrow("label")}
                </th>
                <th className="px-2 py-1">Fields</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((f) => (
                <tr
                  key={f.file_number}
                  onClick={() =>
                    nav.go({ page: "file-detail", fileNumber: f.file_number })
                  }
                  className="cursor-pointer border-b hover:bg-blue-50 dark:hover:bg-gray-800"
                >
                  <td className="px-2 py-1 font-mono">{f.file_number}</td>
                  <td className="px-2 py-1">{f.label}</td>
                  <td className="px-2 py-1 text-gray-500">
                    {Object.keys(f.fields ?? {}).length || "—"}
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
