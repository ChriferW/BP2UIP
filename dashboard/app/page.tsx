import Link from "next/link";
import { readAnalysis, readProcessViews } from "@/lib/artifacts";

export const dynamic = "force-dynamic";

export default function Home() {
  const views = readProcessViews();
  const analysis = readAnalysis();
  const approved = views.filter((v) => v.spec?.status === "approved").length;
  const drafts = views.filter((v) => v.spec?.status === "draft").length;
  const candidates = views.reduce(
    (n, v) =>
      n +
      (v.uplift?.findings.filter((f) => f.classification === "AGENTIC_CANDIDATE").length ??
        0),
    0,
  );

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6 py-16">
      <h1 className="font-mono text-3xl font-bold tracking-tight">BP2UIP</h1>
      <p className="text-neutral-300">
        A migration compiler for RPA estates: Blue Prism in, modernized
        UiPath out, with the reasoning shown. This dashboard renders the
        pipeline&apos;s JSON artifacts and computes nothing itself.
      </p>
      {views.length > 0 ? (
        <ul className="space-y-2 text-sm text-neutral-300">
          <li>
            <Link href="/estate" className="underline underline-offset-4 hover:text-white">
              Estate explorer
            </Link>
            : {views.length} processes with complexity scores and the
            dependency graph{analysis ? "" : " (run `bp2uip analyze` for scores)"}.
          </li>
          <li>
            <Link href="/uplift" className="underline underline-offset-4 hover:text-white">
              Uplift map
            </Link>
            : {candidates} agentic candidate{candidates === 1 ? "" : "s"} found
            across the estate, every finding citing its criteria.
          </li>
          <li>
            <Link href="/review" className="underline underline-offset-4 hover:text-white">
              Intent review
            </Link>
            : {approved} approved, {drafts} awaiting review. Check each claim
            against its cited stages and approve with your name recorded to
            provenance.
          </li>
        </ul>
      ) : (
        <p className="text-sm text-neutral-500">
          No artifacts found; run the pipeline first.
        </p>
      )}
      <p className="text-sm text-neutral-500">
        Progress and design decisions are logged in the repository:{" "}
        <a
          className="underline hover:text-neutral-300"
          href="https://github.com/ChriferW/BP2UIP"
        >
          github.com/ChriferW/BP2UIP
        </a>
      </p>
    </main>
  );
}
