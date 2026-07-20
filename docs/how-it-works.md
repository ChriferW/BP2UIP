# How BP2UIP works

A walkthrough of what the application actually does, end to end,
written to be explainable out loud. For the build order see
`docs/roadmap.md`; for the design arguments see `docs/master-plan.md`.

## The one-paragraph version

BP2UIP treats RPA migration as compilation. A Blue Prism release
export goes in; the pipeline parses it into a structured model of the
estate, uses an LLM to extract what each process is actually for, puts
that extraction in front of a human for approval, and then generates
UiPath artifacts and design documents from the approved intent rather
than from the raw XML. Every step leaves a verifiable record of where
its output came from.

## The pipeline at a glance

```
.bprelease XML
      |
      v
  parse ............ estate.json          (built, week 2)
      |
      v
  extract .......... intent-spec.json     (built, week 3)
      |
      v
  review ........... approved spec        (built, week 3)
      |
      v
  analyze .......... uplift report        (roadmap week 4)
      |
      v
  generate ......... PDD, SDD, UiPath     (roadmap weeks 5-7)
```

Each arrow is a CLI command (`bp2uip parse`, `extract`, `review`, and
later `generate` and `report`). Commands that are not built yet say so
and exit; nothing pretends to work.

## What a .bprelease file is

When you export from Blue Prism you get a single XML file containing
everything the export included: processes, business objects, work
queues, environment variables, credentials metadata. The fixtures in
`fixtures/` are real exports from Blue Prism 7 of a fictional bank
estate authored for this project (they were designed and validated in
the product, never run).

The structure that matters:

- A **process** is a flowchart: a set of stages (decision,
  calculation, action, loop, exception handling) plus the links
  between them. Links are not stored as a separate list; each stage
  carries the id of the stage it flows to next, with `ontrue` and
  `onfalse` branches for decisions.
- A **business object** is a library of actions (each action is itself
  a small flowchart) that processes call, typically wrapping one
  application such as a core banking system.
- A **work queue** is Blue Prism's unit of workload: items with a key
  field, retry limit, and status, which processes feed and consume.
- Some of the process's meaning is stored as **geometry**. An
  exception-handling Block is literally a rectangle with x, y, width,
  height; the stages it protects are whichever stages are drawn inside
  it. The XML gives you nothing else to go on.

## Step 1: parsing (`bp2uip parse`)

`parser.py` reads one or more .bprelease files and produces one JSON
document, the estate model (`schema/estate.schema.json`). What it does:

- Walks each component in the release and builds processes (stages,
  data items, links, descriptions), objects (their published actions),
  and queues (name, key field, max attempts). Components shared
  between files are deduplicated by their Blue Prism id.
- Maps Blue Prism's stage types onto a stable vocabulary
  (`decision`, `calculation`, `queue_read`, and so on), always keeping
  the original type string verbatim in `raw_type`.
- Recognizes calls to Blue Prism's built-in Work Queues object and
  classifies them as queue reads and writes, extracting the queue name
  from the action's inputs. This matters later: queue interactions are
  where the process's transactional shape lives.
- Resolves exception Blocks geometrically: point-in-rectangle
  containment decides which stages a Block covers and which Recover
  stage handles their exceptions.
- Pairs loop starts with loop ends and computes which stages are
  inside the loop body by walking the links.
- Records the sha256 of every source file, so the estate document
  states exactly which bytes it was derived from.

The honesty mechanism: anything the parser sees but does not
understand goes into an `unparsed` list in the output instead of being
silently dropped. Things the parser deliberately skips (the info boxes
Blue Prism draws on every page, Studio folder groupings) are decisions
documented in the build log, not gaps. Against the current fixtures,
`unparsed` is empty.

The parser also does not care about cosmetic noise in the source. One
fixture contains a stage named "Stage Dsipute Row", a genuine typo
from the authoring session, kept because real ten-year-old estates are
full of them.

## Step 2: intent extraction (`bp2uip extract`)

The XML says how a process works. It does not say why, and migrating
the how reproduces a decade of workarounds on a new platform. So the
pipeline extracts intent: for one process, it serializes the parsed
structure (plus the objects and queues that process references) into a
prompt and asks an LLM to state the process's purpose, inputs,
outputs, business rules, exception semantics, and human touchpoints.

The controls around the LLM are the point:

- **Citations.** Every claim must cite the id of at least one stage
  that supports it. `validate_spec` checks that every cited stage
  actually exists in the estate. A spec that asserts something the
  source does not evidence is rejected, and the provider gets one
  chance to correct itself before the run fails. See
  `docs/intent-spec.md` for the full format.
- **A pluggable provider interface.** All LLM access goes through
  `providers.py` (Anthropic implemented, OpenAI stubbed). No other
  module may call an LLM SDK. API keys come from environment variables
  only (populated from a local gitignored .env file at CLI startup;
  copy `.env.example` to get started); artifacts record provider and
  model names, never credentials.
- **A versioned prompt.** Each spec records which prompt version and
  which exact model string produced it, so extraction quality can be
  compared across prompt iterations.
- **Deterministic tests.** The test suite uses a fake provider with
  canned responses; no test calls a real API.

## Step 3: the review gate (`bp2uip review`)

Extraction always produces a draft. A human reads the spec, checks its
claims against the cited stages, and approves it:

    bp2uip review artifacts/<process>/intent-spec.json --approve --by "Name"

The reviewer identity is required and never inferred from git config
or the environment. The invariant the whole project hangs on: nothing
downstream generates from a draft. Forcing generation from an
unapproved spec will be possible but permanently recorded as
unreviewed.

## Provenance

Every process gets an append-only JSONL log (`provenance.py`). Each
event (parsed, extraction run, spec drafted, spec approved, later
generation) carries the sha256 of the previous line, so editing or
deleting history is detectable. Combined with the file hashes in the
artifacts, any generated output can be traced back through the
approved spec and the extraction run to the exact source bytes.

## What is not built yet

Analysis and scoring (week 4), the dashboard (week 4), PDD/SDD
generation (week 5), and UiPath artifact generation, meaning
REFramework scaffolding and Maestro BPMN (weeks 6-7). The CLI stubs
for these state what they will do and exit. The build logs in
`docs/build-log/` record week by week what was actually built, what
broke, and what was decided, including the parts that went wrong.

## Where things live

| Path | What it is |
|---|---|
| `fixtures/` | Blue Prism release exports of the fictional Meridian estate |
| `schema/` | JSON Schemas for every artifact type |
| `pipeline/src/bp2uip/` | parser, model, intent extraction, providers, provenance, CLI |
| `pipeline/tests/` | the test suite; fixtures are parsed, never executed |
| `docs/` | master plan, roadmap, this document, the build logs |
| `artifacts/` | pipeline output: estate model, intent specs, provenance logs |
