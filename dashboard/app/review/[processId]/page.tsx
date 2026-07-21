import Link from "next/link";
import { notFound } from "next/navigation";
import { SpecStatusBadge } from "@/components/badges";
import { ReviewScreen, type StageRow } from "@/components/review-screen";
import type { Stage } from "@/lib/artifacts";
import { readProcessViews } from "@/lib/artifacts";

export const dynamic = "force-dynamic";

function stageDetail(stage: Stage): string {
  const props = stage.properties ?? {};
  if (stage.type === "decision") return String(props.expression ?? "");
  if (stage.type === "action") return `${props.object ?? "?"} :: ${props.action ?? "?"}`;
  if (stage.type === "queue_read" || stage.type === "queue_write") {
    const queue = props.queue_name ? ` on ${props.queue_name}` : "";
    return `${props.action ?? ""}${queue}`;
  }
  if (stage.type === "calculation") return String(props.expression ?? "");
  if (stage.type === "exception") {
    return `${props.exception_type ?? "exception"}: ${props.detail ?? ""}`;
  }
  if (stage.type === "loop_start") return `for each ${props.collection ?? "?"}`;
  return "";
}

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ processId: string }>;
}) {
  const { processId } = await params;
  const view = readProcessViews().find((v) => v.process.id === processId);
  if (!view || !view.spec) notFound();
  const { process, spec } = view;

  const stages: StageRow[] = process.stages.map((s) => ({
    id: s.id,
    name: s.name,
    type: s.type,
    detail: stageDetail(s),
  }));

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <p className="text-sm">
        <Link href="/review" className="text-neutral-500 hover:text-neutral-300">
          Intent review
        </Link>
        <span className="text-neutral-600"> / </span>
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-2xl font-bold">{process.name}</h1>
        <SpecStatusBadge status={spec.status} />
      </div>
      <p className="mt-2 text-sm text-neutral-400">
        Spec <code>{spec.spec_id}</code>, extracted by {spec.extraction.provider}/
        {spec.extraction.model} (prompt v{spec.extraction.prompt_version}).
      </p>
      <ReviewScreen processId={process.id} spec={spec} stages={stages} />
    </main>
  );
}
