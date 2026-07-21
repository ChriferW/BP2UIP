import Link from "next/link";
import { notFound } from "next/navigation";
import {
  BandBadge,
  ClassificationBadge,
  SpecStatusBadge,
} from "@/components/badges";
import type { Classification } from "@/lib/artifacts";
import { readProcessViews } from "@/lib/artifacts";

export const dynamic = "force-dynamic";

export default async function ProcessPage({
  params,
}: {
  params: Promise<{ processId: string }>;
}) {
  const { processId } = await params;
  const view = readProcessViews().find((v) => v.process.id === processId);
  if (!view) notFound();
  const { process, complexity, dependencies, spec, uplift } = view;

  const classificationByStage = new Map<string, Classification>();
  for (const finding of uplift?.findings ?? []) {
    for (const stageId of finding.stage_ids) {
      classificationByStage.set(stageId, finding.classification);
    }
  }

  const metrics: [string, string | number][] = complexity
    ? [
        ["Score", complexity.score],
        ["Stages", complexity.stage_count],
        ["Logic stages", complexity.logic_stage_count],
        ["Decisions", complexity.decision_count],
        ["Branching depth", complexity.branching_depth],
        ["Loops", complexity.loop_count],
        ["Object calls", complexity.object_call_count],
        ["Queue operations", complexity.queue_operation_count],
        ["Exception constructs", complexity.exception_construct_count],
        ["Exception density", complexity.exception_density.toFixed(3)],
      ]
    : [];

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <p className="text-sm">
        <Link href="/estate" className="text-neutral-500 hover:text-neutral-300">
          Estate
        </Link>
        <span className="text-neutral-600"> / </span>
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-2xl font-bold">{process.name}</h1>
        {complexity && <BandBadge band={complexity.band} />}
        <SpecStatusBadge status={spec?.status ?? null} />
      </div>
      {spec && (
        <p className="mt-2 text-sm text-neutral-400">
          Spec <code>{spec.spec_id}</code>, extracted by {spec.extraction.provider}/
          {spec.extraction.model} (prompt v{spec.extraction.prompt_version})
          {spec.approval
            ? `, approved by ${spec.approval.approved_by}`
            : ", awaiting review"}
          .
        </p>
      )}

      {complexity && (
        <section className="mt-8">
          <h2 className="font-mono text-lg font-bold">Complexity</h2>
          <dl className="mt-3 grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-5">
            {metrics.map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-neutral-500">{label}</dt>
                <dd className="font-mono">{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {dependencies && (
        <section className="mt-8">
          <h2 className="font-mono text-lg font-bold">Dependencies</h2>
          <div className="mt-3 grid gap-4 text-sm sm:grid-cols-2">
            <div className="rounded border border-neutral-800 p-4">
              <h3 className="font-mono text-xs text-neutral-500">Objects</h3>
              {dependencies.objects.length ? (
                <ul className="mt-2 space-y-1">
                  {dependencies.objects.map((o) => (
                    <li key={o.object}>
                      {o.object}
                      <span className="text-neutral-500"> ({o.actions.join(", ")})</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-neutral-500">None.</p>
              )}
            </div>
            <div className="rounded border border-neutral-800 p-4">
              <h3 className="font-mono text-xs text-neutral-500">Queues</h3>
              {dependencies.queues.length ? (
                <ul className="mt-2 space-y-1">
                  {dependencies.queues.map((q) => (
                    <li key={q.queue}>
                      <span className="font-mono">{q.queue}</span>
                      <span className="text-neutral-500">
                        {" "}
                        ({q.reads} reads, {q.adds} adds, {q.dispositions} dispositions)
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-neutral-500">None.</p>
              )}
            </div>
          </div>
        </section>
      )}

      <section className="mt-8">
        <h2 className="font-mono text-lg font-bold">Stages</h2>
        <p className="mt-1 text-sm text-neutral-400">
          {uplift
            ? "Classifications from the uplift analyzer; start, end, and note stages carry no behavior and are unclassified."
            : "No uplift analysis for this process yet."}
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-800 font-mono text-xs text-neutral-500">
              <tr>
                <th className="py-2 pr-4">Stage</th>
                <th className="py-2 pr-4">Type</th>
                <th className="py-2">Classification</th>
              </tr>
            </thead>
            <tbody>
              {process.stages.map((stage) => {
                const classification = classificationByStage.get(stage.id);
                return (
                  <tr key={stage.id} className="border-b border-neutral-900">
                    <td className="py-2 pr-4">{stage.name}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-neutral-400">
                      {stage.type}
                    </td>
                    <td className="py-2">
                      {classification ? (
                        <ClassificationBadge classification={classification} />
                      ) : (
                        <span className="text-xs text-neutral-600">-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
