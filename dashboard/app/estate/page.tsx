import Link from "next/link";
import { BandBadge, SpecStatusBadge } from "@/components/badges";
import { readAnalysis, readProcessViews } from "@/lib/artifacts";

export const dynamic = "force-dynamic";

export default function EstatePage() {
  const views = readProcessViews();
  const analysis = readAnalysis();

  if (views.length === 0) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="font-mono text-2xl font-bold">Estate</h1>
        <p className="mt-4 text-neutral-400">
          No estate artifacts found. Run <code>bp2uip parse</code> in the
          pipeline first; this dashboard only renders what the pipeline
          wrote.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="font-mono text-2xl font-bold">Estate</h1>
      <p className="mt-2 text-sm text-neutral-400">
        {views.length} processes. Complexity is an ordinal ranking with
        documented weights, not an effort estimate;{" "}
        {analysis
          ? `analyzed ${analysis.analyzed_at.slice(0, 10)}.`
          : "no analysis artifact found, run `bp2uip analyze`."}
      </p>

      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-neutral-800 font-mono text-xs text-neutral-500">
            <tr>
              <th className="py-2 pr-4">Process</th>
              <th className="py-2 pr-4">Band</th>
              <th className="py-2 pr-4 text-right">Score</th>
              <th className="py-2 pr-4 text-right">Stages</th>
              <th className="py-2 pr-4 text-right">Decisions</th>
              <th className="py-2 pr-4 text-right">Exc. density</th>
              <th className="py-2 pr-4">Spec</th>
              <th className="py-2">Uplift findings</th>
            </tr>
          </thead>
          <tbody>
            {views.map(({ process, complexity, spec, uplift }) => {
              const candidates =
                uplift?.findings.filter((f) => f.classification === "AGENTIC_CANDIDATE")
                  .length ?? null;
              const gates =
                uplift?.findings.filter((f) => f.classification === "HUMAN_GATE").length ??
                null;
              return (
                <tr
                  key={process.id}
                  className="border-b border-neutral-900 hover:bg-neutral-900/50"
                >
                  <td className="py-3 pr-4">
                    <Link
                      href={`/estate/${process.id}`}
                      className="text-neutral-100 underline-offset-4 hover:underline"
                    >
                      {process.name}
                    </Link>
                  </td>
                  <td className="py-3 pr-4">
                    {complexity ? <BandBadge band={complexity.band} /> : "-"}
                  </td>
                  <td className="py-3 pr-4 text-right font-mono">
                    {complexity?.score ?? "-"}
                  </td>
                  <td className="py-3 pr-4 text-right font-mono">
                    {complexity?.stage_count ?? "-"}
                  </td>
                  <td className="py-3 pr-4 text-right font-mono">
                    {complexity?.decision_count ?? "-"}
                  </td>
                  <td className="py-3 pr-4 text-right font-mono">
                    {complexity?.exception_density.toFixed(2) ?? "-"}
                  </td>
                  <td className="py-3 pr-4">
                    <SpecStatusBadge status={spec?.status ?? null} />
                  </td>
                  <td className="py-3 font-mono text-xs text-neutral-400">
                    {uplift
                      ? `${candidates} candidate${candidates === 1 ? "" : "s"}, ${gates} gate${gates === 1 ? "" : "s"}`
                      : "not analyzed"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {analysis && analysis.dependencies.queue_couplings.length > 0 && (
        <section className="mt-10">
          <h2 className="font-mono text-lg font-bold">Queue couplings</h2>
          <p className="mt-1 text-sm text-neutral-400">
            Derived producer/consumer edges: one process feeds a queue
            another works. Never declared in the source, always worth
            knowing before migrating either side alone.
          </p>
          <ul className="mt-3 space-y-2 text-sm">
            {analysis.dependencies.queue_couplings.map((coupling) => {
              const name = (id: string) =>
                views.find((v) => v.process.id === id)?.process.name ?? id;
              return (
                <li key={coupling.queue} className="rounded border border-neutral-800 p-3">
                  <span className="font-mono text-neutral-300">{coupling.queue}</span>
                  <span className="text-neutral-500">: </span>
                  {coupling.producers.map(name).join(", ") || "no producer in estate"}
                  <span className="text-neutral-500"> feeds </span>
                  {coupling.consumers.map(name).join(", ") || "no consumer in estate"}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </main>
  );
}
