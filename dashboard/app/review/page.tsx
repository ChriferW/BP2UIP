import Link from "next/link";
import { SpecStatusBadge } from "@/components/badges";
import { readProcessViews } from "@/lib/artifacts";

export const dynamic = "force-dynamic";

export default function ReviewIndexPage() {
  const views = readProcessViews();

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="font-mono text-2xl font-bold">Intent review</h1>
      <p className="mt-2 text-sm text-neutral-400">
        The gate the pipeline hangs on: a human checks every extracted claim
        against the stages it cites before anything downstream generates.
        Draft specs are waiting for that check.
      </p>
      <ul className="mt-6 space-y-2">
        {views.map(({ process, spec }) => (
          <li
            key={process.id}
            className="flex items-center justify-between rounded border border-neutral-800 p-4"
          >
            <div>
              {spec ? (
                <Link
                  href={`/review/${process.id}`}
                  className="underline-offset-4 hover:underline"
                >
                  {process.name}
                </Link>
              ) : (
                <span className="text-neutral-400">{process.name}</span>
              )}
              {spec?.approval && (
                <span className="ml-3 text-xs text-neutral-500">
                  approved by {spec.approval.approved_by}
                </span>
              )}
              {!spec && (
                <span className="ml-3 text-xs text-neutral-600">
                  no spec extracted yet
                </span>
              )}
            </div>
            <SpecStatusBadge status={spec?.status ?? null} />
          </li>
        ))}
      </ul>
    </main>
  );
}
