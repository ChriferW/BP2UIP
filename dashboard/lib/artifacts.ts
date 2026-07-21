// Server-side readers for the pipeline's JSON artifacts. The dashboard
// is a viewer: it renders what the pipeline wrote and computes nothing
// itself. Shapes mirror the JSON Schemas in schema/; only the fields
// the dashboard renders are typed here.

import fs from "node:fs";
import path from "node:path";

const ARTIFACTS_DIR = path.resolve(process.cwd(), "..", "artifacts");

export interface Stage {
  id: string;
  name: string;
  type: string;
}

export interface Process {
  id: string;
  name: string;
  description: string;
  stages: Stage[];
}

export interface Estate {
  processes: Process[];
  objects: { id: string; name: string }[];
  queues: { id: string; name: string; key_field: string | null; max_attempts: number | null }[];
  source: { parsed_at: string };
}

export interface ComplexityScore {
  process_id: string;
  process_name: string;
  stage_count: number;
  logic_stage_count: number;
  decision_count: number;
  branching_depth: number;
  loop_count: number;
  object_call_count: number;
  distinct_objects: string[];
  queue_operation_count: number;
  exception_construct_count: number;
  exception_density: number;
  score: number;
  band: "low" | "medium" | "high";
}

export interface ProcessDependencies {
  process_id: string;
  process_name: string;
  objects: { object: string; actions: string[] }[];
  queues: { queue: string; reads: number; adds: number; dispositions: number }[];
  subprocesses: string[];
}

export interface EstateAnalysis {
  analyzed_at: string;
  complexity: ComplexityScore[];
  dependencies: {
    processes: ProcessDependencies[];
    object_fan_in: { object: string; used_by: string[] }[];
    queue_couplings: { queue: string; producers: string[]; consumers: string[] }[];
  };
}

export interface IntentSpec {
  spec_id: string;
  process_id: string;
  status: "draft" | "approved";
  extraction: { provider: string; model: string; prompt_version: string };
  approval: { approved_by: string; approved_at: string } | null;
}

export type Classification = "AGENTIC_CANDIDATE" | "KEEP_DETERMINISTIC" | "HUMAN_GATE";

export interface UpliftFinding {
  id: string;
  stage_ids: string[];
  classification: Classification;
  reasoning: string;
  criteria: string[];
}

export interface UpliftReport {
  process_id: string;
  spec_ref: { spec_id: string; status_at_analysis: "draft" | "approved" };
  analyzed_at: string;
  criteria_version: string;
  findings: UpliftFinding[];
}

function readJson<T>(...segments: string[]): T | null {
  const file = path.join(ARTIFACTS_DIR, ...segments);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf-8")) as T;
}

export function slug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function readEstate(): Estate | null {
  return readJson<Estate>("estate", "estate.json");
}

export function readAnalysis(): EstateAnalysis | null {
  return readJson<EstateAnalysis>("estate", "analysis.json");
}

export function readSpec(processName: string): IntentSpec | null {
  return readJson<IntentSpec>(slug(processName), "intent-spec.json");
}

export function readUplift(processName: string): UpliftReport | null {
  return readJson<UpliftReport>(slug(processName), "uplift.json");
}

export interface ProcessView {
  process: Process;
  complexity: ComplexityScore | null;
  dependencies: ProcessDependencies | null;
  spec: IntentSpec | null;
  uplift: UpliftReport | null;
}

export function readProcessViews(): ProcessView[] {
  const estate = readEstate();
  if (!estate) return [];
  const analysis = readAnalysis();
  return estate.processes.map((process) => ({
    process,
    complexity: analysis?.complexity.find((c) => c.process_id === process.id) ?? null,
    dependencies:
      analysis?.dependencies.processes.find((d) => d.process_id === process.id) ?? null,
    spec: readSpec(process.name),
    uplift: readUplift(process.name),
  }));
}

/** Map every stage id in the estate to "name (type)" for citation display. */
export function stageIndex(estate: Estate): Map<string, string> {
  const index = new Map<string, string>();
  for (const process of estate.processes) {
    for (const stage of process.stages) {
      index.set(stage.id, `${stage.name} (${stage.type})`);
    }
  }
  return index;
}
