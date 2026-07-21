# Week 4: The analysis layer

Date: 2026-07-20

## What happened

The estate became navigable and the uplift thesis became visible, in
the order the roadmap demanded: docs/uplift-criteria.md was written
before the analyzer, the analyzer implements the document, and a
contract test asserts every rule ID the code emits exists in the
document. Policy changes now have to go through the doc.

`bp2uip analyze` is live. Estate-wide it produces complexity scores
(a weighted ordinal ranking over stage counts, decisions, loops,
object calls, queue operations, and exception constructs, banded
low/medium/high, explicitly not an effort estimate) and the dependency
graph: objects and queues per process, object fan-in, and derived
producer/consumer couplings. Per process it produces the uplift
report: every behavioral stage classified KEEP_DETERMINISTIC,
AGENTIC_CANDIDATE, or HUMAN_GATE, one finding per rationale, with a
tested coverage invariant that no stage is silently skipped. All of
it is pure code over the estate model and the reviewed spec; no LLM
is involved in analysis. Each report records the criteria version and
appends an uplift_analyzed event to the process's provenance chain.

Against the real estate: Card Dispute Intake scores 66 (high),
Settlement Reconciliation 18 (medium), the other two low, which is
the order a migration backlog should take. The graph derived the edge
the source never declares: Dispute Feeder produces the Q-Disputes
queue that Card Dispute Intake consumes, so migrating either side
alone breaks the pair. Three agentic candidates were found, each with
cited reasoning: the exact-match transaction reconciliation (AC-1),
and two threshold-into-human-review decisions (AC-3), ReviewThreshold
in disputes and Tolerance in reconciliation.

P04 Daily Settlement Reconciliation was extracted against the real
API (valid and fully cited on the first attempt), reviewed, and
approved, so all four processes now have approved specs. Its
provenance chain shows the honest sequence: analyzed as a draft,
approved, re-analyzed as approved.

The dashboard got its first real pages, reading the JSON artifacts
and computing nothing itself: an estate explorer with the complexity
table and queue couplings, a per-process page with the score
breakdown, dependencies, and a classification badge on every stage,
and an uplift map grouping all findings with their reasoning and
criteria IDs.

Milestone check from the roadmap: Tier 1 substantially complete. On
schedule.

## Where the analyzer earned some trust, and where it should not have any

- AC-3 (threshold-only triage into a human gate) was designed against
  the dispute intake's ReviewThreshold decision, and then fired
  unmodified on the reconciliation process's variance-tolerance
  decision. A rule generalizing to a process it was not written
  against is the first evidence the criteria are rules rather than
  descriptions of one fixture.
- The negative case held too: "Retry Limit Reached?" also compares
  against configuration, but routes to retry machinery rather than a
  human gate, and correctly stayed deterministic.
- The trust boundary, stated plainly: the detectors are shape
  heuristics over expressions and stage types, tested against this
  fixture estate only. AC-2 (unstructured input interpretation), the
  strongest agentic candidate class in real estates, has no detector
  at all yet; the document says so instead of pretending. A real
  estate will produce misses and false positives, which is why
  findings are inputs to a design review, not decisions.

## What broke or surprised me

- Making `criteria_version` a required field on the uplift report
  broke two gate tests that construct reports directly. Fine this
  week because no uplift artifacts existed anywhere before it, but it
  is the concrete reminder that required-field additions are breaking
  for producers even when the schema philosophy calls field additions
  non-breaking. After emitters exist, additions like this need a
  default or a version bump.
- Blue Prism stores most queue writes without a queue name (Mark
  Exception and Mark Completed act on the current item), so the
  dependency graph has to attribute them. The rule chosen: attribute
  to the process's read queue when it reads exactly one, otherwise
  leave unattributed rather than guess.
- A direction correction from Chris worth recording: the dashboard's
  eventual purpose is the primary user surface, where users upload a
  release and approve or deny specs, not a read-only artifact viewer.
  The build order stays as planned for now (the week 5 review screen
  is the first step toward that), but the destination is the
  interaction loop, which will eventually need the dashboard to
  invoke the pipeline rather than just read artifacts/.

## Decisions made

- `analyze` is a new CLI subcommand. The master plan's CLI surface
  listed parse, extract, review, generate, report; the addition is
  flagged here rather than made silently.
- Estate analysis is a sixth artifact type with its own schema,
  example, and contract-test entry (the master plan named five).
  Complexity and the dependency graph belong together in one
  estate-wide document; uplift stays per-process next to the spec it
  analyzed.
- HG-1 claims only handoff-shaped stages (action, queue write,
  exception) from the spec's cited human touchpoints. A decision
  stage cited as touchpoint evidence is routing, not the handoff, and
  stays eligible for AC-3. This is the split that lets a threshold
  decision be an agentic candidate while the gate it feeds stays a
  human gate.
- A configuration constant is defined structurally: a data item with
  a non-empty scalar initial value that no stage writes. That
  distinguishes ReviewThreshold from RetryCount without name
  heuristics.
- The complexity score's weights and bands live in one place in
  analysis.py and the artifact self-describes as an ordinal ranking.
  No effort-days are claimed anywhere.

## Next

Week 5: the governance story becomes concrete. The dashboard
intent-review screen (source stages and spec side by side, approval
recorded to provenance), PDD and SDD generators from approved specs
with the gate enforced in code, and the modernization report that
pulls this week's analysis into a per-process recommendation.
