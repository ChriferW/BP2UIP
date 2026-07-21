# Week 5: The governance story becomes concrete

Date: 2026-07-20

## What happened

The review gate stopped being a promise and became enforced code, and
the tool now produces the two documents an RPA intake process actually
requires. `bp2uip generate` writes the PDD (as-is) and SDD (to-be)
from an approved spec, `bp2uip report` writes the estate-wide
modernization report, and every process directory gains a
`manifest.json` indexing its artifacts with hashes. The full Tier 1
flow ran against the whole fixture estate: parse, extract, review,
analyze, generate, report, with all four provenance chains verifying
the complete story from extraction run to report generation.

The gate behavior, precisely: `generate` refuses a draft spec.
`--force` exists for demos, appends an `unreviewed_generation` event
to provenance before anything is written, and the forced document
carries a header saying it came from a draft. Approval requires both
the spec document and the provenance log to agree; a spec document
edited to claim approval that provenance does not confirm is refused.

The documents earn their keep by being derived, not written. The PDD
reads the trigger off the queue configuration (Q-Disputes, key field
DisputeRef, max 3 attempts) and walks the flow in link order with
true branches first. The SDD derives the target architecture from
queue usage (the intake is a REFramework performer, the feeder a
dispatcher, and the coupling between them is flagged so neither
migrates alone), maps the exception taxonomy, tables every uplift
finding as a design input, and ends with an explicit human-build TODO
list for what the export cannot provide: selectors, credentials, and
a decision per agentic candidate. The modernization report's wave
logic produced the right non-obvious answer: the Dispute Feeder is
the simplest process in the estate (score 8) and still lands in wave
3, because it feeds the queue the hardest process consumes.

The dashboard grew the intent-review screen, the first real piece of
the direction recorded last week (the dashboard as the surface where
users review and approve). Extracted claims sit next to the source
stages, clicking a claim highlights the stages it cites, and approval
takes a typed reviewer name. The approve action invokes the pipeline
CLI rather than reimplementing approval, so the lifecycle transition
and the provenance hash chain have exactly one implementation.

119 tests pass; the suite grew by 11 (docsgen and the generate/report
CLI paths).

## What broke or surprised me

- Nothing broke outright this week; the surprises were dependencies
  and gaps worth recording. The dashboard's approve action spawns
  `pipeline/.venv/bin/bp2uip`, the launcher that is patched locally
  for the macOS hidden-flag problem. That workaround now has a third
  dependent: if the package is ever pip-reinstalled, the CLI and the
  dashboard approve button break together until the launcher is
  re-patched.
- DOCX output is conditional and currently untested: pandoc is not
  installed on this machine and not in CI, so every generated
  document this week is markdown only, with the CLI saying so at
  generation time. The roadmap's committed reference template does
  not exist yet either. Honest status: the DOCX path is written but
  has never produced a file.
- Replacing the `generate`/`report` stubs invalidated the stub tests
  that asserted "not implemented" output, a small reminder that
  honest stubs have tests too, and implementing the real thing means
  rewriting them, not deleting them (the remaining `--xaml`/`--bpmn`
  stubs keep theirs).

## Decisions made

- Dashboard approval shells out to the CLI. Reimplementing the
  lifecycle transition in TypeScript would mean two implementations
  of the provenance chain that could drift; the dashboard stays a
  surface over the one engine. Reviewer identity comes from a typed
  form field, never inferred, same rule as the CLI.
- Rejecting a spec in the review screen means leaving it a draft:
  nothing downstream generates from it, which is the gate doing its
  job. Per-section corrections (the `spec_corrected` event and the
  approval `changes` list exist in the model for exactly this) are
  deferred, and the screen says so.
- `generate_report` does not pass the gate. It generates nothing from
  spec content beyond status and counts, and it reports drafts as
  drafts; gating it would hide the very state a migration lead needs
  to see. PDD and SDD, which do restate spec content, are gated.
- The manifest is regenerated at generation time from what actually
  exists on disk, never from what should exist. An absent artifact is
  an absent key.
- Generator signatures gained an `out_dir` keyword over the master
  plan's interface sketch; flagged here rather than silently changed.
- `report_generated` is appended to each included process's log, so a
  process's chain records every document that speaks for it.

## Next

Week 6: the back end. The Jinja2 emitter framework and real UiPath
artifacts: REFramework .xaml scaffolding, Config.xlsx, queue
manifests, with explicit TODO markers wherever human judgment is
required. The emitters are the remaining consumers of the gate, and
the first test of whether the intent spec carries enough to generate
from.
