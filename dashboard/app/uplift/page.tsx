import Link from "next/link";
import { CLASSIFICATION_LABELS, ClassificationBadge } from "@/components/badges";
import type { Classification, UpliftFinding } from "@/lib/artifacts";
import { readEstate, readProcessViews, stageIndex } from "@/lib/artifacts";

export const dynamic = "force-dynamic";

const ORDER: Classification[] = ["AGENTIC_CANDIDATE", "HUMAN_GATE", "KEEP_DETERMINISTIC"];

const INTROS: Record<Classification, string> = {
  AGENTIC_CANDIDATE:
    "Steps that encode a judgment call as brittle deterministic logic. Candidates for agentic designs with deterministic fallbacks, not mandates.",
  HUMAN_GATE:
    "Steps that hand work to a human or leave it in a state a human must resolve. Migration preserves these boundaries.",
  KEEP_DETERMINISTIC:
    "The default. Rule-following steps that should be rebuilt as conventional automation.",
};

export default function UpliftPage() {
  const estate = readEstate();
  const views = readProcessViews().filter((v) => v.uplift !== null);
  const index = estate ? stageIndex(estate) : new Map<string, string>();

  if (views.length === 0) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="font-mono text-2xl font-bold">Uplift map</h1>
        <p className="mt-4 text-neutral-400">
          No uplift reports found. Run <code>bp2uip analyze</code> in the
          pipeline first.
        </p>
      </main>
    );
  }

  const grouped = new Map<
    Classification,
    { processName: string; processId: string; finding: UpliftFinding }[]
  >(ORDER.map((c) => [c, []]));
  for (const view of views) {
    for (const finding of view.uplift!.findings) {
      grouped.get(finding.classification)!.push({
        processName: view.process.name,
        processId: view.process.id,
        finding,
      });
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="font-mono text-2xl font-bold">Uplift map</h1>
      <p className="mt-2 text-sm text-neutral-400">
        Every behavioral stage of every analyzed process, classified by the
        rules in{" "}
        <a
          className="underline hover:text-neutral-200"
          href="https://github.com/ChriferW/BP2UIP/blob/main/docs/uplift-criteria.md"
        >
          docs/uplift-criteria.md
        </a>
        . The analyzer is pure code over the estate model and the reviewed
        spec; the default answer is deterministic and anything else carries
        its reasoning.
      </p>

      {ORDER.map((classification) => {
        const entries = grouped.get(classification)!;
        return (
          <section key={classification} className="mt-10">
            <div className="flex items-center gap-3">
              <h2 className="font-mono text-lg font-bold capitalize">
                {CLASSIFICATION_LABELS[classification]}s
              </h2>
              <span className="font-mono text-sm text-neutral-500">{entries.length}</span>
            </div>
            <p className="mt-1 text-sm text-neutral-400">{INTROS[classification]}</p>
            <div className="mt-4 space-y-3">
              {entries.map(({ processName, processId, finding }) => (
                <article
                  key={`${processId}-${finding.id}`}
                  className="rounded border border-neutral-800 p-4"
                >
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <Link
                      href={`/estate/${processId}`}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {processName}
                    </Link>
                    <ClassificationBadge classification={finding.classification} />
                    {finding.criteria.map((rule) => (
                      <span
                        key={rule}
                        className="rounded bg-neutral-900 px-1.5 py-0.5 font-mono text-xs text-neutral-400"
                      >
                        {rule}
                      </span>
                    ))}
                  </div>
                  <p className="mt-2 text-sm text-neutral-300">{finding.reasoning}</p>
                  <p className="mt-2 text-xs text-neutral-500">
                    Stages:{" "}
                    {finding.stage_ids.map((id) => index.get(id) ?? id).join("; ")}
                  </p>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </main>
  );
}
