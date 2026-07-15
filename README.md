# BP2UIP

**A migration compiler for RPA estates: Blue Prism in, modernized UiPath out, with the reasoning shown.**

BP2UIP parses Blue Prism release exports, extracts the *business intent*
behind each process, and regenerates that intent as idiomatic UiPath:
REFramework-based workflows, Maestro BPMN orchestration, and
configuration manifests. Along the way it produces an audit-grade record
of every translation decision and a modernization report that identifies
where deterministic steps are candidates for agentic uplift, and where
they are not.

> Migration tools move code. BP2UIP moves *intent*, and shows its work.

## The problem

Enterprises that adopted RPA early are sitting on large Blue Prism
estates and a strategic mandate to consolidate onto modern platforms.
The naive approach of transpiling stages one-to-one produces bad UiPath,
because the two platforms think differently: different exception
models, different reuse idioms, different orchestration semantics.
Practitioners consistently report that migration is really
*re-architecture*, which is why most estates move slowly, by hand,
process by process.

Three things make this worse in regulated environments:

1. **No provenance.** When a process is rebuilt by hand, the mapping
   between old and new lives in a developer's head. An auditor asking
   "prove the new automation does what the old one did" gets a shrug.
2. **No modernization signal.** A migration is the single best moment
   to ask whether each step should stay deterministic or is a genuine
   candidate for agentic automation, and no existing tool asks it.
3. **No estate view.** Prioritizing hundreds of processes for migration
   requires complexity, dependency, and value data that lives buried in
   XML nobody reads.

## What BP2UIP does

BP2UIP is architected as a **compiler**:

```
        .bprelease XML                 (Blue Prism release export)
              |
              v
   +---------------------+
   |  FRONT-END: Parser  |   lxml-based; normalizes processes, objects,
   |                     |   stages, data items, exception blocks into
   |                     |   a platform-neutral estate model
   +----------+----------+
              |
              v
   +---------------------+
   |  IR: Intent Spec    |   LLM-assisted extraction of what each
   |                     |   process is FOR: inputs, outputs, business
   |                     |   rules, exception semantics, human
   |                     |   touchpoints. A reviewable artifact, with
   |                     |   every claim citing source stage IDs
   +----------+----------+
              |
              v
   +---------------------+
   |  BACK-END: Emitters |   generates UiPath artifacts from intent,
   |                     |   not from syntax:
   |                     |   - REFramework-based .xaml scaffolding
   |                     |   - Maestro BPMN for orchestration-shaped
   |                     |     processes
   |                     |   - config / queue / asset manifests
   |                     |   - explicit TODO markers where human
   |                     |     judgment is required; honesty is a
   |                     |     feature, not a gap
   +----------+----------+
              |
              v
   +---------------------+
   |  ANALYSIS LAYER     |   - complexity & migration-effort scoring
   |                     |   - dependency graphing across the estate
   |                     |   - agentic-uplift recommendations, with
   |                     |     reasoning, per step: AGENTIC CANDIDATE /
   |                     |     KEEP DETERMINISTIC / HUMAN GATE
   |                     |   - migration wave planning
   +----------+----------+
              |
              v
      Migration Provenance Record      (append-only, per process:
                                        source -> intent -> output,
                                        every decision cited)
```

The **intermediate representation is business intent, not syntax.**
That is the core design bet. A stage-by-stage transpiler faithfully
reproduces 2015's architecture on a 2026 platform. Intent extraction
regenerates the process the way a good developer would rebuild it,
except the reasoning is captured, reviewable, and auditable instead of
living in someone's head.

## The dashboard

A Next.js application over the pipeline's artifacts:

- **Estate explorer**: every process and object in the parsed estate,
  with complexity scores, dependency graphs, and migration status
- **Intent review**: the human checkpoint. Side-by-side source stages
  and extracted intent spec, approve/annotate before generation
- **Uplift map**: where the estate's agentic candidates are, with the
  reasoning for each recommendation and each exclusion
- **Provenance viewer**: the full decision trail for any migrated
  process, reconstructable on demand

The pipeline is the compiler; the dashboard is its IDE.

## Governance posture

BP2UIP treats migration as a regulated activity, because in a bank it
is one:

- **Intent specs are review gates.** No generation happens from an
  unreviewed spec. The human approval is recorded on the provenance
  record.
- **Every generated element cites its sources.** Each workflow,
  decision, and rule in the output traces to named Blue Prism stages.
- **Uplift recommendations are conservative by design.** A step is
  flagged agentic-candidate only when judgment demonstrably changes the
  outcome; policy-unambiguous logic is explicitly marked KEEP
  DETERMINISTIC, with reasoning. The tool's default answer is
  determinism.
- **The provenance record is append-only** and structured for the
  examiner's question: how do you know the new system does what the
  old one did?

## Demo estate

`fixtures/` contains the **Meridian Financial Group legacy estate**: a
set of authored Blue Prism processes exported as real `.bprelease`
files, modeled on the back-office workloads a regional bank actually
runs (payment investigations, account maintenance, dispute intake,
report reconciliation). Meridian is the same fictional institution as
[the three-build automation portfolio](https://github.com/ChriferW/MeridianBank_Project)
that precedes this project. The story continues: the merger closed,
and the acquired back office runs on Blue Prism.

## Status & roadmap

**In active development (started July 2026). Building in public.**

| Tier | Scope | Status |
|---|---|---|
| 1 | Parser -> estate model; intent extraction; estate dashboard; modernization report with uplift analysis | In progress |
| 2 | .xaml generation for the common stage vocabulary (sequences, decisions, calculations, exception blocks -> REFramework skeleton) | Planned |
| 3 | Maestro BPMN emission; end-to-end round trip: one Blue Prism process to a running, governance-annotated UiPath solution | Planned |

Progress, findings, and design decisions are logged in
[`docs/build-log/`](docs/build-log/) as the build proceeds, including
the honest account of what doesn't work.

## Tech stack

| Layer | Choice |
|---|---|
| Pipeline | Python 3.12: `lxml` parsing, Pydantic estate model, CLI entry point |
| Intent extraction | LLM via pluggable provider interface: Anthropic (primary), OpenAI; provider-agnostic by design |
| Emitters | Jinja2-templated .xaml / BPMN / JSON manifest generation |
| Dashboard | Next.js 15, TypeScript, Tailwind CSS |
| Contract | Versioned JSON artifact schema between pipeline and dashboard |
| Fixtures | Blue Prism (authored + exported sample estate), Python fixture tooling |

## Repository layout

```
bp2uip/
├── README.md                        <- you are here
├── pipeline/                        Python: parser, intent, emitters, analysis
│   ├── src/bp2uip/                  package source
│   ├── tests/
│   └── pyproject.toml
├── dashboard/                       Next.js: estate explorer, intent review,
│   │                                uplift map, provenance viewer
│   └── package.json
├── schema/                          versioned JSON artifact contracts
├── fixtures/                        the Meridian legacy estate (.bprelease)
└── docs/
    ├── architecture.md              the compiler design, in depth
    ├── intent-spec.md               the IR format specification
    ├── uplift-criteria.md           when a step earns AGENTIC CANDIDATE
    └── build-log/                   dated engineering notes, honest ones
```

## Author

Christopher Williams · c.williams1011@proton.me
GitHub: [@ChriferW](https://github.com/ChriferW)

All companies, processes, and data in the demo estate are fictional.
No credentials are committed; LLM providers are configured via
environment variables.
