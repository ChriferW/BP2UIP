"use server";

// The approval server action invokes the pipeline CLI rather than
// reimplementing approval: there is exactly one implementation of the
// lifecycle transition and the provenance hash chain, and it lives in
// the pipeline. The dashboard is the surface, not a second engine.

import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { revalidatePath } from "next/cache";
import { readEstate, slug } from "./artifacts";

const run = promisify(execFile);

export interface ApproveState {
  ok: boolean | null;
  message: string;
}

export async function approveSpec(
  _prev: ApproveState,
  formData: FormData,
): Promise<ApproveState> {
  const processId = String(formData.get("processId") ?? "");
  const reviewer = String(formData.get("reviewer") ?? "").trim();
  if (!reviewer) {
    return {
      ok: false,
      message: "Reviewer name is required; approval identity is never inferred.",
    };
  }
  const estate = readEstate();
  const proc = estate?.processes.find((p) => p.id === processId);
  if (!proc) {
    return { ok: false, message: "Process not found in the estate." };
  }
  const repoRoot = path.resolve(process.cwd(), "..");
  const cli = path.join(repoRoot, "pipeline", ".venv", "bin", "bp2uip");
  const specPath = path.join(repoRoot, "artifacts", slug(proc.name), "intent-spec.json");
  if (!fs.existsSync(cli)) {
    return {
      ok: false,
      message:
        "Pipeline CLI not found at pipeline/.venv/bin/bp2uip; approve from the CLI instead.",
    };
  }
  try {
    const { stdout } = await run(
      cli,
      ["review", specPath, "--approve", "--by", reviewer],
      { cwd: repoRoot },
    );
    revalidatePath("/review");
    revalidatePath(`/review/${processId}`);
    revalidatePath("/estate");
    revalidatePath("/");
    return { ok: true, message: stdout.trim() };
  } catch (error) {
    const failure = error as { stdout?: string; message?: string };
    return {
      ok: false,
      message: (failure.stdout || failure.message || "approval failed").trim(),
    };
  }
}
