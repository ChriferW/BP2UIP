"use client";

import { useActionState, useEffect, useMemo, useState } from "react";
import { approveSpec, type ApproveState } from "@/lib/actions";
import type { IntentSpec } from "@/lib/artifacts";

export interface StageRow {
  id: string;
  name: string;
  type: string;
  detail: string;
}

interface Claim {
  section: string;
  title: string;
  body: string;
  citations: string[];
}

function claimsOf(spec: IntentSpec): Claim[] {
  const claims: Claim[] = [
    {
      section: "Purpose",
      title: "Purpose",
      body: spec.purpose.text,
      citations: spec.purpose.citations,
    },
  ];
  for (const item of spec.inputs) {
    claims.push({
      section: "Inputs",
      title: item.name,
      body: item.description + (item.source ? ` (source: ${item.source})` : ""),
      citations: item.citations,
    });
  }
  for (const item of spec.outputs) {
    claims.push({
      section: "Outputs",
      title: item.name,
      body:
        item.description + (item.destination ? ` (destination: ${item.destination})` : ""),
      citations: item.citations,
    });
  }
  for (const rule of spec.business_rules) {
    claims.push({
      section: "Business rules",
      title: rule.id,
      body: rule.statement,
      citations: rule.citations,
    });
  }
  for (const semantic of spec.exception_semantics) {
    claims.push({
      section: "Exception semantics",
      title: `When ${semantic.condition}`,
      body: semantic.current_handling,
      citations: semantic.citations,
    });
  }
  for (const touchpoint of spec.human_touchpoints) {
    claims.push({
      section: "Human touchpoints",
      title: "Touchpoint",
      body: touchpoint.description,
      citations: touchpoint.citations,
    });
  }
  return claims;
}

const INITIAL: ApproveState = { ok: null, message: "" };

export function ReviewScreen({
  processId,
  spec,
  stages,
}: {
  processId: string;
  spec: IntentSpec;
  stages: StageRow[];
}) {
  const [highlighted, setHighlighted] = useState<string[]>([]);
  const [state, formAction, pending] = useActionState(approveSpec, INITIAL);
  const claims = useMemo(() => claimsOf(spec), [spec]);
  const stageName = useMemo(
    () => new Map(stages.map((s) => [s.id, s.name])),
    [stages],
  );

  useEffect(() => {
    if (highlighted.length > 0) {
      document
        .getElementById(`stage-${highlighted[0]}`)
        ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [highlighted]);

  let lastSection = "";
  return (
    <div className="mt-6 grid gap-8 lg:grid-cols-2">
      <section>
        <h2 className="font-mono text-lg font-bold">Extracted claims</h2>
        <p className="mt-1 text-sm text-neutral-400">
          Click a claim to highlight the source stages it cites. The
          reviewer&apos;s job: does the evidence actually support the claim?
        </p>
        <div className="mt-4 space-y-2">
          {claims.map((claim, i) => {
            const header =
              claim.section !== lastSection ? (
                <h3 className="mt-5 mb-2 font-mono text-xs text-neutral-500">
                  {claim.section}
                </h3>
              ) : null;
            lastSection = claim.section;
            const active = claim.citations.some((c) => highlighted.includes(c));
            return (
              <div key={i}>
                {header}
                <button
                  type="button"
                  onClick={() => setHighlighted(claim.citations)}
                  className={`w-full rounded border p-3 text-left text-sm transition-colors ${
                    active
                      ? "border-amber-700 bg-amber-950/30"
                      : "border-neutral-800 hover:border-neutral-600"
                  }`}
                >
                  {claim.title !== claim.section && (
                    <span className="font-medium">{claim.title}: </span>
                  )}
                  {claim.body}
                  <span className="mt-2 block text-xs text-neutral-500">
                    cites:{" "}
                    {claim.citations.map((c) => stageName.get(c) ?? c).join("; ")}
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      </section>

      <section className="lg:sticky lg:top-4 lg:self-start">
        <h2 className="font-mono text-lg font-bold">Source stages</h2>
        <p className="mt-1 text-sm text-neutral-400">
          Every stage of the parsed process; cited stages light up.
        </p>
        <div className="mt-4 max-h-[70vh] overflow-y-auto rounded border border-neutral-800">
          <table className="w-full text-left text-sm">
            <tbody>
              {stages.map((stage) => (
                <tr
                  key={stage.id}
                  id={`stage-${stage.id}`}
                  className={
                    highlighted.includes(stage.id)
                      ? "bg-amber-950/40"
                      : "border-neutral-900"
                  }
                >
                  <td className="border-b border-neutral-900 px-3 py-2">{stage.name}</td>
                  <td className="border-b border-neutral-900 px-3 py-2 font-mono text-xs text-neutral-400">
                    {stage.type}
                  </td>
                  <td className="border-b border-neutral-900 px-3 py-2 font-mono text-xs text-neutral-500">
                    {stage.detail}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-6 rounded border border-neutral-800 p-4">
          {spec.status === "approved" && spec.approval ? (
            <p className="text-sm text-emerald-300">
              Approved by <strong>{spec.approval.approved_by}</strong> at{" "}
              {spec.approval.approved_at}. Recorded in the provenance chain.
            </p>
          ) : (
            <form action={formAction} className="space-y-3">
              <input type="hidden" name="processId" value={processId} />
              <label className="block text-sm text-neutral-300">
                Reviewer name (recorded to provenance, never inferred)
                <input
                  name="reviewer"
                  type="text"
                  required
                  className="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
                  placeholder="Your name"
                />
              </label>
              <button
                type="submit"
                disabled={pending}
                className="rounded bg-emerald-800 px-4 py-2 text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
              >
                {pending ? "Approving..." : "Approve this spec"}
              </button>
              <p className="text-xs text-neutral-500">
                Approval runs the pipeline CLI, the single implementation of
                the lifecycle transition. To reject, leave the spec a draft:
                nothing downstream generates from it. Per-section corrections
                are not built yet; edit via re-extraction for now.
              </p>
            </form>
          )}
          {state.message && (
            <p
              className={`mt-3 text-sm ${state.ok ? "text-emerald-300" : "text-red-300"}`}
            >
              {state.message}
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
