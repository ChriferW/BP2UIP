# BP2UIP: 8-Week Milestone Plan

Working rule for the whole plan: **every week ends with something a
visitor to the repo can see.** The interview team may click the link at
any moment; the repo should never look stalled. Commit early, commit
often, write the build-log entry before closing the week.

Second rule: **the Parallels window is Week 1 only.** Author the entire
fixture estate in one or two painful sessions, export everything, and
never depend on Blue Prism again. If a fixture is missing later, edit
the XML by hand.

---

## Week 1: Repo bones + the fixture estate

**Goal: the repo exists, the email can be sent, and Blue Prism is never needed again.**

- Create the repo: README, directory skeleton, LICENSE, first build-log entry
- Author the Meridian legacy estate in Blue Prism (one or two Parallels sessions):
  - 6 to 8 processes of graded complexity, bank-shaped: dispute intake,
    payment investigation, account maintenance, report reconciliation
  - At least one process with: a decision tree, a calculation block, a
    loop, an exception block, a sub-object call, and a queue interaction
    (these become the parser's test matrix)
- Export all as .bprelease, commit to `fixtures/`
- Skim the XML, write `docs/build-log/week1.md` on the format's anatomy
- **Send the announcement email once the repo has 3+ days of commits**

Visitor sees: real fixtures, a professional README, an engineering log.

## Week 2: The front end (parser)

**Goal: .bprelease in, clean estate model out.**

- Python package scaffold (`pipeline/`, pyproject, pytest, CI via GitHub Actions)
- lxml parser: processes, objects, stages, data items, links, exception blocks
- Pydantic estate model (the platform-neutral representation)
- CLI: `bp2uip parse fixtures/*.bprelease -> estate.json`
- Unit tests against every fixture; parser coverage table in the build log

Visitor sees: green CI badge, tests, a real artifact schema forming.

## Week 3: The IR (intent extraction)

**Goal: the design bet made real. One process becomes a reviewable intent spec.**

- Define the intent-spec format (`docs/intent-spec.md`): purpose, inputs,
  outputs, business rules, exception semantics, human touchpoints, with
  every claim citing source stage IDs. Spec must be rich enough to drive
  PDD/SDD generation in Week 5 (design for it now)
- Spec lifecycle: draft -> approved. Nothing downstream runs on a draft
- Pluggable LLM provider interface (Anthropic first, OpenAI stub)
- Extraction pipeline: estate model chunk -> prompt -> validated intent spec
  (value-domain validation on the output, naturally)
- Run against 2 to 3 fixtures; commit the specs so reviewers can judge quality
- Build-log entry: where extraction was wrong and how the prompt evolved
  (this honesty is the project's voice)

Visitor sees: actual intent specs next to their source XML. This is the
week the project stops being a parser and becomes a thesis.

## Week 4: The analysis layer + first dashboard cut

**Goal: the estate becomes navigable and the uplift thesis becomes visible.**

- Complexity and migration-effort scoring (stage counts, branching depth,
  object fan-in, exception density)
- Dependency graph across processes and shared objects
- Uplift analyzer v1: per-step classification AGENTIC CANDIDATE /
  KEEP DETERMINISTIC / HUMAN GATE, with cited reasoning
  (`docs/uplift-criteria.md` written first, code implements the doc)
- Next.js dashboard scaffold: estate explorer reading the JSON artifacts,
  complexity table, dependency view (simple first, pretty later)

Visitor sees: screenshots in the README, a dashboard taking shape.

**Milestone check: end of Week 4 = Tier 1 substantially complete.**
If behind, cut dashboard polish, never the provenance work.

## Week 5: Provenance, intent review gate, and PDD/SDD generation

**Goal: the governance story becomes concrete, and the tool starts
producing the documents an RPA intake process actually requires.**

- Append-only migration provenance record: source -> intent -> decisions,
  one record per process, schema documented
- Dashboard intent-review screen: source stages and extracted spec side
  by side, confirm/correct/annotate per section; approval (who, when,
  what changed) recorded to provenance. This is the gate: PDD, SDD, and
  emitters all refuse to run on unapproved specs (CLI `--force` exists
  for demos and is itself logged as an unreviewed generation)
- **PDD generator**: as-is process document from parser output + approved
  intent (purpose, trigger, inputs/outputs, current-state flow, business
  rules, current exception handling, systems, human touchpoints).
  Markdown + DOCX output
- **SDD generator**: to-be design document from approved intent + emitter
  plan (target UiPath architecture and why, queue/config design,
  exception taxonomy mapping, per-step uplift decisions with reasoning,
  human-build TODO list, provenance references). Markdown + DOCX output
- Modernization report generator: per-process summary of complexity,
  uplift findings, and migration recommendation
- Run the full Tier 1 flow on the entire fixture estate; commit all
  artifacts including generated PDDs/SDDs

Visitor sees: point the tool at a legacy process, get back the two
documents intake requires, pre-written and cited. The auditable-migration
story working end to end.

## Week 6: The back end (emitters, Tier 2)

**Goal: BP2UIP generates real UiPath artifacts.**

- Jinja2 emitter framework
- .xaml generation for the mapped vocabulary: sequences, decisions,
  calculations, assignments, exception blocks -> REFramework skeleton
  with Config.xlsx and queue manifests
- Explicit TODO markers wherever human judgment is required, each one
  citing the intent-spec clause it comes from
- Import a generated project into UiPath Studio (Community tenant);
  document what imports cleanly and what does not, honestly

Visitor sees: generated .xaml in the repo, an import screenshot, and a
frank build-log entry about the gap between generated and hand-built.

## Week 7: The homerun swing (Tier 3)

**Goal: one complete round trip.**

- Pick the best-behaved mid-complexity fixture process
- Maestro BPMN emission for its orchestration shape
- Drive it to actually running on the Community tenant: import, wire
  connections, execute against sample data
- Record the demo (short screen capture, linked in README)
- Uplift demo: show one step the analyzer flagged AGENTIC CANDIDATE,
  explain what the agentic version would do and why the rest stays
  deterministic

Visitor sees: a Blue Prism process that now runs as governed UiPath,
with the entire decision trail inspectable. The socks come off here.

**Fallback if Week 7 overruns:** the round trip demo slips to Week 8 and
polish is cut. The demo is the priority; polish is negotiable.

## Week 8: Hardening, docs, and the second email

**Goal: the repo reads as finished work, and the team hears about it.**

- `docs/architecture.md`: the compiler design written properly
- README refresh: real screenshots, demo video link, updated status table
- Test pass, CI green, code cleanup, tag v0.1.0
- Final build-log entry: what worked, what didn't, what Phase 2 would be
  (estate-scale batch processing, more stage vocabulary, deeper BPMN)
- Send the follow-up email to Krishna/team: project complete, demo link,
  two-paragraph summary of findings

Visitor sees: a shipped project with a version tag and a demo.

---

## Standing weekly rhythm

- Commit at least 3 days per week, even if small
- One build-log entry per week, dated, honest
- Never let the README describe something that doesn't exist yet;
  the status table is the only place futures live

## Risk register

| Risk | Mitigation |
|---|---|
| .bprelease format harder to parse than expected | Week 1 XML skim surfaces this early; scope parser to the fixture vocabulary, not the universal format |
| Intent extraction quality unconvincing | Specs are human-reviewable by design; publish imperfect specs with corrections as build-log content. The honesty IS the differentiator |
| .xaml generation rabbit hole | Emit the mapped vocabulary only; TODO markers are a feature. Never chase universal coverage |
| Community tenant limitation blocks the round trip | Document the limitation and demo everything up to the blocked step; note what an enterprise tenant would allow |
| Life happens, a week slips | Tier 1 (Weeks 1-5) is a complete impressive project on its own; Tiers 2-3 are upside |
