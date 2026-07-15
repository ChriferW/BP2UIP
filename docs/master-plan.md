# BP2UIP Master Plan

Status: draft for review. This document records the architecture
decisions, artifact contracts, module breakdown, and testing strategy
for the 8-week build described in [roadmap.md](roadmap.md). The README
and the roadmap are the source of truth for scope and sequencing; this
document turns them into an implementation plan. Where something is
underspecified, it appears in the Open Questions section at the end
rather than being silently assumed.

---

## 1. Architecture decision records

### ADR-001: Monorepo with three top-level components

**Decision.** One repository containing:

```
pipeline/     Python 3.12 package: the compiler itself
dashboard/    Next.js 15 + TypeScript + Tailwind: the compiler's IDE
schema/       versioned JSON Schema files: the contract between them
fixtures/     the Meridian legacy estate (.bprelease exports)
docs/         specs, build log, this plan
```

**Rationale.** The pipeline and dashboard never import each other's
code. They share only data, and that data crosses the boundary as JSON
files validated against the schemas in `schema/`. A monorepo keeps the
contract, its producer, and its consumer in one place, in one commit
history, which matters for a build-in-public project where a visitor
should be able to trace any artifact to the code that produced it.

**Consequences.** CI runs two independent jobs (Python lint/test,
dashboard build). A schema change is only complete when the same commit
updates the Pydantic models, the schema file, and any dashboard types
that read it.

### ADR-002: The pipeline is a compiler

**Decision.** The Python package is organized as a classical compiler:

- **Front-end (parser).** `.bprelease` XML in, platform-neutral estate
  model out. The parser knows Blue Prism; nothing downstream does.
- **IR (intent spec).** The intermediate representation is business
  intent, not syntax: what the process is for, its inputs, outputs,
  rules, exception semantics, and human touchpoints, with every claim
  citing source stage IDs. Produced by LLM-assisted extraction,
  validated, and gated by human review.
- **Back-end (emitters).** UiPath artifacts generated from the approved
  intent spec, not from the source syntax: REFramework .xaml
  scaffolding, Maestro BPMN, config and queue manifests.
- **Analysis layer.** Complexity scoring, dependency graphing, and
  agentic-uplift classification. Reads the estate model and intent
  specs; feeds the modernization report and the dashboard.

**Rationale.** This is the core design bet stated in the README: a
stage-by-stage transpiler reproduces old architecture on a new
platform, while intent extraction regenerates the process the way a
developer would rebuild it, with the reasoning captured. The compiler
framing also gives clean module seams that match the roadmap weeks
(front-end week 2, IR week 3, analysis week 4, back-end week 6).

**Consequences.** No module except `parser` may read `.bprelease`
content. No module except `emitters` and `docsgen` may produce output
artifacts. The IR is the only path between them.

### ADR-003: Data flows through files, not function calls

**Decision.** Each pipeline stage reads and writes JSON artifacts on
disk. The CLI orchestrates stages; the dashboard reads the same files.

```
fixtures/*.bprelease
    | bp2uip parse
    v
estate model JSON  (whole estate)
    | bp2uip extract <process>
    v
intent spec JSON   (status: draft)
    | review: human approves or corrects   <- THE GATE
    v
intent spec JSON   (status: approved)  +  provenance events
    | bp2uip generate <process>            (refuses drafts; --force logs
    v                                       an unreviewed_generation event)
PDD / SDD / .xaml / BPMN / manifests   +  provenance events
    | bp2uip report
    v
modernization report
```

**Rationale.** Files make every intermediate inspectable and
committable, which the roadmap requires (committed specs in week 3,
committed PDDs/SDDs in week 5, committed .xaml in week 6). They also
decouple the dashboard completely: it is a reader of artifacts, not a
client of the pipeline.

**Consequences.** Every artifact type needs a schema and a
`schema_version` field. Artifact locations must be predictable; the
manifest (section 2.5) is the index.

### ADR-004: The review gate is a single choke point

**Decision.** One function, `bp2uip.gate.require_approved(spec, log,
force=False)`, is the only way generation begins. PDD generation, SDD
generation, and every emitter call it first. It raises on a draft
spec. With `force=True` it proceeds but first appends an
`unreviewed_generation` event to the provenance log; a forced run that
cannot write provenance does not run.

**Rationale.** The governance posture in the README ("no generation
happens from an unreviewed spec") is only credible if it cannot be
bypassed by calling an inner function. Making the gate a required
parameter-bearing call in every generator's entry path, tested
directly, bakes the invariant into the interfaces from day one.

**Consequences.** Generator signatures accept the provenance log, not
just the spec, so the forced path can always be recorded. Tests assert
both refusal and forced-run logging before any generator has a real
implementation.

### ADR-005: LLM access through one provider interface

**Decision.** All LLM calls go through `bp2uip.providers.LLMProvider`
(a small protocol: complete a prompt, return text plus usage
metadata). `AnthropicProvider` is implemented first; `OpenAIProvider`
is a stub with the same shape. A factory selects the provider by name.
API keys come from environment variables only (`ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`); no key ever appears in code, config files, or
artifacts. Artifacts record which provider and model produced them,
never the credentials.

**Consequences.** `bp2uip.intent` depends on the protocol, not on any
SDK. Tests use a `FakeProvider` that returns canned responses, so
extraction logic is testable without network access.

### ADR-006: Provenance is an append-only event log per process

**Decision.** One provenance file per process, JSON Lines format, one
event per line. Events are never edited or deleted; corrections are
new events. Each event carries a sequence number and the hash of the
previous event, forming a verifiable chain (see Open Question 7 on
whether the hash chain ships in v1).

**Rationale.** The README frames provenance as the answer to an
examiner's question. Append-only JSONL is trivially auditable, diffs
cleanly in git, and makes tampering visible in history.

### ADR-007: Parser is designed now, implemented against real fixtures

**Decision.** The parser's public interface, error types, and output
model are defined in the scaffold. The implementation is an honest
stub that raises `NotImplementedError` until real `.bprelease` exports
land in `fixtures/`. No field of the XML format is guessed. The estate
model (which is ours, not Blue Prism's) carries two honesty
mechanisms: every stage keeps its verbatim `raw_type` string from the
XML, and an `unparsed` list records any element the parser saw but did
not understand.

---

## 2. Versioned JSON artifact schema, first draft

General conventions, applied to every artifact type:

- Every document carries `schema_version` (semver string). Breaking
  shape changes bump the major/minor; the dashboard refuses documents
  whose version it does not know.
- Schema files live in `schema/`, one per artifact type, JSON Schema
  draft 2020-12. Pydantic models in the pipeline are the same shapes;
  a contract test asserts they agree.
- All IDs are strings. All timestamps are UTC ISO 8601.
- Field lists below are the draft contract. The estate model in
  particular will gain fields when real fixtures arrive; additions are
  non-breaking, renames are breaking.

### 2.1 Estate model (`schema/estate.schema.json`)

The platform-neutral output of the parser. One document per parse run,
covering the whole estate.

```json
{
  "schema_version": "0.1.0",
  "source": {
    "files": [{ "path": "fixtures/x.bprelease", "sha256": "..." }],
    "parsed_at": "2026-07-20T00:00:00Z",
    "parser_version": "0.1.0"
  },
  "processes": [
    {
      "id": "proc-...",
      "name": "Dispute Intake",
      "description": "",
      "stages": [
        {
          "id": "stage-...",
          "name": "...",
          "type": "decision",
          "raw_type": "<verbatim type string from the XML>",
          "properties": {}
        }
      ],
      "data_items": [
        { "id": "...", "name": "...", "data_type": "...", "initial_value": null }
      ],
      "links": [{ "from_stage": "...", "to_stage": "...", "label": null }],
      "exception_blocks": [
        { "id": "...", "covers_stages": ["..."], "handler_stage": "..." }
      ]
    }
  ],
  "objects": [
    { "id": "...", "name": "...", "actions": [{ "id": "...", "name": "...", "stages": [] }] }
  ],
  "queues": [{ "id": "...", "name": "..." }],
  "unparsed": [
    { "element": "<xml element name>", "location": "...", "note": "not yet handled" }
  ]
}
```

`stage.type` is a normalized enum (decision, calculation, action,
loop_start, loop_end, exception, subprocess_call, queue_read,
queue_write, note, start, end, unknown). The enum is deliberately
provisional until the week 1 XML skim; `raw_type` preserves the truth
regardless.

### 2.2 Intent spec (`schema/intent-spec.schema.json`)

The IR. One document per process. Sections match `docs/intent-spec.md`
(to be written in week 3); this schema is the container and lifecycle.

```json
{
  "schema_version": "0.1.0",
  "spec_id": "spec-...",
  "process_id": "proc-...",
  "estate_ref": { "path": "...", "sha256": "..." },
  "status": "draft",
  "created_at": "...",
  "extraction": {
    "provider": "anthropic",
    "model": "...",
    "prompt_version": "..."
  },
  "purpose": { "text": "...", "citations": ["stage-..."] },
  "inputs": [
    { "name": "...", "description": "...", "source": "...", "citations": ["stage-..."] }
  ],
  "outputs": [
    { "name": "...", "description": "...", "destination": "...", "citations": [] }
  ],
  "business_rules": [
    { "id": "BR-1", "statement": "...", "citations": ["stage-..."] }
  ],
  "exception_semantics": [
    { "condition": "...", "current_handling": "...", "citations": [] }
  ],
  "human_touchpoints": [
    { "description": "...", "citations": [] }
  ],
  "approval": null
}
```

Lifecycle rules, enforced in schema (conditional) and in code:

- `status` is `draft` or `approved`. Nothing else.
- `status: "approved"` requires a non-null `approval` object:
  `{ "approved_by": "...", "approved_at": "...", "changes": [ { "section": "...", "before": "...", "after": "...", "note": "..." } ] }`
- Every `citations` array element must be a stage ID that exists in
  the referenced estate document. This is checked by
  `intent.validate_spec`, not by JSON Schema.
- Approval also appends a `spec_approved` event to provenance; the
  spec file and the provenance log must agree, and `gate` checks both.

### 2.3 Provenance record (`schema/provenance-event.schema.json`)

JSON Lines: the schema describes one line. One file per process,
append-only.

```json
{
  "schema_version": "0.1.0",
  "process_id": "proc-...",
  "seq": 4,
  "prev_hash": "sha256 of the previous line, or null for seq 1",
  "timestamp": "...",
  "actor": "who or what did this",
  "event": "spec_approved",
  "detail": {}
}
```

Event vocabulary (extensible, additions non-breaking): `parsed`,
`extraction_run`, `spec_drafted`, `spec_corrected`, `spec_approved`,
`generation`, `unreviewed_generation`, `report_generated`. `detail`
carries event-specific fields, for example the artifact paths and
hashes a `generation` event produced, or the diff summary a
`spec_corrected` event applied.

### 2.4 Uplift finding (`schema/uplift-finding.schema.json`)

One document per process holding a list of findings; each finding
classifies one step or step group.

```json
{
  "schema_version": "0.1.0",
  "process_id": "proc-...",
  "spec_ref": { "spec_id": "...", "status_at_analysis": "approved" },
  "analyzed_at": "...",
  "findings": [
    {
      "id": "UF-1",
      "stage_ids": ["stage-..."],
      "classification": "KEEP_DETERMINISTIC",
      "reasoning": "...",
      "criteria": ["UC-2"]
    }
  ]
}
```

`classification` is exactly one of `AGENTIC_CANDIDATE`,
`KEEP_DETERMINISTIC`, `HUMAN_GATE`. `criteria` references rule IDs in
`docs/uplift-criteria.md` (week 4; the doc is written before the code
that implements it). Default classification is deterministic; the
analyzer must justify any other answer, per the README's governance
posture.

### 2.5 Manifest (`schema/manifest.schema.json`)

The index that ties one process's artifacts together. Regenerated
whenever an artifact for the process is produced.

```json
{
  "schema_version": "0.1.0",
  "process_id": "proc-...",
  "process_name": "...",
  "generated_at": "...",
  "pipeline_version": "0.1.0",
  "artifacts": {
    "estate": { "path": "...", "sha256": "...", "schema_version": "0.1.0" },
    "intent_spec": { "path": "...", "sha256": "...", "schema_version": "0.1.0", "status": "approved" },
    "uplift": { "path": "...", "sha256": "...", "schema_version": "0.1.0" },
    "provenance": { "path": "...", "events": 12 },
    "pdd": { "path": "...", "sha256": "..." },
    "sdd": { "path": "...", "sha256": "..." },
    "emitted": [{ "kind": "xaml", "path": "...", "sha256": "..." }],
    "report": { "path": "...", "sha256": "..." }
  }
}
```

Absent artifacts are simply absent keys; the manifest never claims an
artifact that does not exist on disk. The dashboard navigates from
manifests.

---

## 3. Python package breakdown (`pipeline/`)

Layout: src layout, `pipeline/src/bp2uip/`, tests in
`pipeline/tests/`, packaging via `pyproject.toml` (hatchling), lint
and format via ruff, tests via pytest. Note: the README's repository
diagram currently shows `pipeline/bp2uip/` (flat layout); see Open
Question 4.

| Module | Responsibility | Roadmap week |
|---|---|---|
| `bp2uip.model` | Pydantic models for every artifact type in section 2; serialization helpers | 2 (estate), 3 (spec), 4 (uplift), 5 (provenance, manifest); shells in scaffold |
| `bp2uip.parser` | `.bprelease` XML to estate model; the only module that reads Blue Prism formats | 2 |
| `bp2uip.providers` | LLM provider protocol, Anthropic implementation, OpenAI stub, fake for tests | 3 |
| `bp2uip.intent` | extraction pipeline (estate chunk to prompt to validated draft spec), citation validation, spec lifecycle transitions | 3 |
| `bp2uip.gate` | the review-gate choke point (ADR-004) | interface in scaffold; enforced from 5 |
| `bp2uip.provenance` | append-only JSONL log: open, append, read, verify | 5 (interface earlier, gate depends on it) |
| `bp2uip.analysis` | complexity scoring, dependency graph, uplift analyzer | 4 |
| `bp2uip.docsgen` | PDD, SDD, modernization report; Markdown first, DOCX second | 5 |
| `bp2uip.emitters` | Jinja2 framework; REFramework .xaml, Maestro BPMN, config/queue manifests | 6 (xaml), 7 (bpmn) |
| `bp2uip.cli` | `bp2uip` entry point: parse, extract, review, generate, report | 2 through 5 |

`bp2uip.gate` and `bp2uip.provenance` are additions to the module list
in the original brief (parser, model, intent, providers, emitters,
analysis, docsgen, cli). They exist as separate modules because the
review-gate invariant (ADR-004) needs a single owner that both
`docsgen` and `emitters` depend on, and provenance is that gate's
witness. Flagged here rather than silently added.

### Public interfaces (draft signatures)

```python
# parser
def parse_release(paths: list[Path]) -> Estate: ...
# scaffold behavior: raises NotImplementedError("built against real
# fixtures; see docs/roadmap.md week 1/2")

# providers
class LLMProvider(Protocol):
    name: str
    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 4096) -> CompletionResult: ...
def get_provider(name: str = "anthropic") -> LLMProvider: ...
# reads API keys from environment; raises ProviderConfigError if unset

# intent
def extract_intent(estate: Estate, process_id: str,
                   provider: LLMProvider) -> IntentSpec:  # status=draft
def validate_spec(spec: IntentSpec, estate: Estate) -> list[SpecError]:
# every citation must name a real stage in the estate
def approve_spec(spec: IntentSpec, *, approved_by: str,
                 changes: list[SpecChange], log: ProvenanceLog) -> IntentSpec:

# gate
def require_approved(spec: IntentSpec, log: ProvenanceLog,
                     *, force: bool = False) -> None:
# raises UnapprovedSpecError on draft unless force;
# force appends an unreviewed_generation event before returning

# provenance
class ProvenanceLog:
    @classmethod
    def open(cls, path: Path, process_id: str) -> "ProvenanceLog": ...
    def append(self, event: ProvenanceEvent) -> None: ...
    def events(self) -> list[ProvenanceEvent]: ...
    def verify(self) -> bool: ...

# analysis
def score_complexity(estate: Estate) -> list[ComplexityScore]: ...
def build_dependency_graph(estate: Estate) -> DependencyGraph: ...
def analyze_uplift(estate: Estate, spec: IntentSpec) -> UpliftReport: ...

# docsgen  (every function calls gate.require_approved first)
def generate_pdd(estate, spec, log, *, force=False) -> GeneratedDoc: ...
def generate_sdd(estate, spec, uplift, log, *, force=False) -> GeneratedDoc: ...
def generate_report(estate, specs, uplift_reports) -> GeneratedDoc: ...

# emitters  (every emitter calls gate.require_approved first)
def emit_reframework(spec, uplift, log, *, force=False) -> EmittedProject: ...
def emit_bpmn(spec, log, *, force=False) -> EmittedArtifact: ...
```

### CLI surface

```
bp2uip parse    <fixtures...> [-o DIR]      week 2
bp2uip extract  <process> [--provider NAME]  week 3
bp2uip review   <spec> [--approve --by NAME] week 3/5 (CLI-side gate)
bp2uip generate <process> [--pdd --sdd --xaml --bpmn] [--force]  weeks 5-7
bp2uip report   [<process>]                  week 5
```

Scaffold behavior: every subcommand parses its arguments, prints one
factual sentence describing what it will do when implemented and which
roadmap week implements it, and exits 0. No fake output, no fake
progress.

---

## 4. Dashboard breakdown (`dashboard/`)

Next.js 15 App Router, TypeScript, Tailwind. The dashboard reads
artifact JSON (validated against `schema/`) and renders it. It is a
reader; the one candidate write path is intent-review approval (Open
Question 2).

| Page | Route | Content | Roadmap week |
|---|---|---|---|
| Landing shell | `/` | project name, one-paragraph description, link out to repo; later a status summary from manifests | scaffold |
| Estate explorer | `/estate` | process/object table with complexity scores and migration status from manifests | 4 |
| Process detail | `/estate/[processId]` | stage listing, dependency view (adjacency list first, graph rendering later) | 4 |
| Uplift map | `/uplift` | findings across the estate grouped by classification, reasoning shown per finding | 4/5 |
| Intent review | `/review/[specId]` | source stages and extracted spec side by side; per-section confirm/correct/annotate; approval recorded to provenance | 5 |
| Provenance viewer | `/provenance/[processId]` | event timeline for one process, chain verification status | 5 |

Shared components: `ArtifactLoader` (reads and schema-checks JSON),
`ProcessTable`, `ComplexityBadge`, `StageList`, `CitationLink` (a
citation in any spec view links to the source stage), `SpecSection`,
`ProvenanceTimeline`, `ClassificationTag`. Simple first, pretty later,
per the roadmap.

---

## 5. Testing strategy

### Parser tests, keyed to the fixture matrix

The roadmap defines 6 to 8 fixture processes and requires at least one
to contain each of: a decision tree, a calculation block, a loop, an
exception block, a sub-object call, a queue interaction. Tests key on
those features, not on fixture count:

| Feature | Test asserts |
|---|---|
| decision tree | decision stages parsed with all outgoing links and labels |
| calculation block | calculation stage with expression captured in properties |
| loop | loop start/end pairing and body membership |
| exception block | covered stages and handler resolved |
| sub-object call | cross-reference from process stage to object action |
| queue interaction | queue read/write stages linked to a named queue |
| whole estate | every fixture parses with zero entries in `unparsed`, or each entry is deliberate and documented in the build log |

One test module per fixture file, plus a table in the week 2 build-log
entry mapping fixture to features covered. Until fixtures land, the
parser test file contains skipped placeholders naming these cases.

### Schema and contract tests

- Every schema file in `schema/` is itself valid JSON Schema
  (metaschema check).
- Every example document embedded in this plan's section 2 validates
  against its schema (examples live in `schema/examples/`).
- Contract test: each Pydantic model serializes to a document that
  validates against the corresponding schema file, so the two
  definitions cannot drift silently.
- Lifecycle test: a spec with `status: "approved"` and `approval:
  null` fails validation, in both JSON Schema and Pydantic.

### Gate tests (exist from the scaffold onward)

- `require_approved` raises `UnapprovedSpecError` on a draft spec.
- `require_approved(force=True)` appends exactly one
  `unreviewed_generation` event and returns.
- `docsgen` and emitter entry points refuse a draft spec even when
  called directly, not only via the CLI.

### Emitter snapshot tests (week 6)

Golden files under `pipeline/tests/snapshots/`. Each emitter run for a
fixture process compares byte-for-byte against the committed snapshot;
an intentional change regenerates snapshots via a pytest flag and the
diff is reviewed in the commit. Timestamps and other run-varying
fields are pinned or excluded so snapshots are deterministic.

### Provenance tests

- Appending preserves prior lines byte-for-byte.
- `verify()` fails if any line is altered or removed.
- Sequence numbers are contiguous.

### CI (`.github/workflows/ci.yml`)

Two jobs on push and pull request:

- `pipeline`: Python 3.12, `ruff check`, `ruff format --check`,
  `pytest`.
- `dashboard`: Node LTS, install, `next build`.

Green CI is a week 2 roadmap deliverable; the scaffold ships with it
already green.

---

## 6. Sequencing notes against the roadmap

- The scaffold (this week) contains interfaces and honest stubs only.
  Nothing in it claims to work; the CLI stubs say what they will do
  and exit. This keeps the README rule intact: the status table is the
  only place futures live.
- The gate and provenance interfaces exist from the scaffold even
  though the roadmap implements provenance in week 5, because ADR-004
  requires generator signatures to carry the gate from day one.
  Interfaces early, implementations on schedule.
- The intent-spec schema (2.2) is deliberately sectioned to feed the
  week 5 PDD/SDD generators, per the roadmap's week 3 instruction to
  design for that now.

## 7. Risks not already in the roadmap register

- **Schema churn once real fixtures arrive.** Mitigation: estate model
  is version 0.1.0 and additive changes are cheap; `raw_type` and
  `unparsed` absorb surprises without breaking the contract.
- **Dashboard approval writeback complicates the architecture** (a
  pure reader is much simpler than a reader-writer). Mitigation:
  decision deferred to Open Question 2; the CLI `review` subcommand is
  the guaranteed-to-exist approval path either way.

---

## 8. Open questions

Decisions needed before or during the scaffold. Stated as questions;
nothing below has been assumed.

1. **Artifact output location.** Where do pipeline outputs live:
   `artifacts/<process-slug>/` at the repo root, committed to git (the
   roadmap requires committing specs, PDDs/SDDs, and .xaml)? If so,
   should `estate.json` (whole-estate, potentially large) also be
   committed, or only per-process slices?
2. **Dashboard approval writeback.** The week 5 intent-review screen
   records approvals. Options: (a) the dashboard shells out to
   `bp2uip review --approve` locally via a Next.js route handler, so
   Python remains the only writer; (b) reimplement spec approval and
   provenance append in TypeScript; (c) dashboard stays read-only in
   v1 and approval is CLI-only, with the review screen displaying but
   not recording. Which one?
3. **Approval identity.** For `approved_by` on a solo project: git
   `user.name`, an environment variable such as `BP2UIP_REVIEWER`, or
   an explicit `--by` argument required on every approval?
4. **src layout vs README diagram.** The brief specifies src layout
   (`pipeline/src/bp2uip/`), but the README's repository diagram shows
   `pipeline/bp2uip/`. Proceed with src layout and update the README
   diagram in the same commit?
5. **License.** The roadmap's week 1 includes a LICENSE file and none
   exists yet. MIT?
6. **Dashboard toolchain.** Package manager (npm, pnpm) and Node
   version for CI (propose Node 22 LTS)?
7. **Provenance hash chain.** Ship `prev_hash` chaining in v1, or
   start with seq + timestamps only and add the chain in week 5? The
   chain is cheap and strengthens the audit story, but it makes any
   hand-editing of committed demo artifacts impossible without
   re-signing.
8. **DOCX generation.** Week 5 requires Markdown + DOCX for PDD/SDD:
   python-docx (pure Python dependency, more layout code) or pandoc
   (better output, external binary dependency in CI)? Decision can
   wait until week 5 but affects the docsgen interface's return type.
9. **LLM defaults.** Default Anthropic model to pin in `extraction`
   metadata (propose the current Sonnet as default with a
   `--model` override), and is `BP2UIP_PROVIDER` an acceptable env var
   for selecting the default provider?
