import { useState, type FormEvent } from "react";
import { useSignon } from "../lib/hooks";

export default function SignonPage({
  onSuccess,
}: {
  onSuccess: () => void;
}) {
  const [access, setAccess] = useState("");
  const [verify, setVerify] = useState("");
  const signon = useSignon();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    signon.mutate(
      { access, verify, site_id: "vehu" },
      { onSuccess },
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-lg border border-gray-300 bg-white p-8 shadow-md dark:border-gray-700 dark:bg-gray-900"
      >
        <h1 className="mb-6 text-2xl font-bold">fm-web</h1>
        <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
          Read-only FileMan browser. Sign on with your VistA ACCESS /
          VERIFY codes.
        </p>

        <label className="mb-1 block text-sm font-medium">ACCESS Code</label>
        <input
          type="text"
          value={access}
          onChange={(e) => setAccess(e.target.value)}
          required
          autoFocus
          className="mb-4 w-full rounded border border-gray-300 px-3 py-2 dark:border-gray-600 dark:bg-gray-800"
        />

        <label className="mb-1 block text-sm font-medium">VERIFY Code</label>
        <input
          type="password"
          value={verify}
          onChange={(e) => setVerify(e.target.value)}
          required
          className="mb-6 w-full rounded border border-gray-300 px-3 py-2 dark:border-gray-600 dark:bg-gray-800"
        />

        <button
          type="submit"
          disabled={signon.isPending}
          className="w-full rounded bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {signon.isPending ? "Signing on..." : "Sign On"}
        </button>

        {signon.isError && (
          <p className="mt-3 text-sm text-red-600">
            {signon.error.detail ?? "Sign-on failed"}
          </p>
        )}
      </form>
    </div>
  );
}
