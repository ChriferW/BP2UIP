# Agentic uplift criteria

Criteria version 0.1.0. Every uplift report records the criteria
version it was analyzed under.

This document is the rule catalog that `bp2uip.analysis.analyze_uplift`
implements. The document comes first: the analyzer cites these rule IDs
in every finding, a contract test asserts that every ID the analyzer
emits exists in this file, and a change in classification policy is a
change to this document before it is a change to code.

## The question being asked

A migration is the one moment an organization looks at every step of
every process and decides what it should become. BP2UIP uses that
moment to ask, per step or step group: should this stay deterministic,
is it a genuine candidate for agentic automation, or is it a point
where a human is in the loop today and must remain so?

The three classifications:

| Classification | Meaning |
|---|---|
| `KEEP_DETERMINISTIC` | The step is rule-following by nature. Rebuild it as conventional automation; introducing a model here adds risk and removes auditability for no benefit. |
| `AGENTIC_CANDIDATE` | The step encodes a judgment call as brittle deterministic logic. An agent with a deterministic fallback and human escalation could do the job the logic approximates. A candidate, not a mandate: the finding is input to a design decision, not the decision. |
| `HUMAN_GATE` | The step exists to hand work to a human or to leave work in a state a human must resolve. Migration must preserve the boundary, whatever else changes around it. |

## Default and precedence

- **P-1.** The default classification is `KEEP_DETERMINISTIC`. A step
  that matches no other rule is deterministic and the finding cites
  P-1. The analyzer must justify any other answer; it never has to
  justify the default.
- **P-2.** When rules from different classifications match the same
  stage, `HUMAN_GATE` wins over `AGENTIC_CANDIDATE`, which wins over
  `KEEP_DETERMINISTIC`. A human boundary is never automated away by a
  finding, and a judgment signal is never silenced by the default. In
  v1 the human-gate rules only claim action, queue write, and
  exception stages, so the HG/AC conflict cannot arise yet; the
  precedence is stated for when the rule sets grow.
- **P-3.** A step that moves money or writes state to a system of
  record is never `AGENTIC_CANDIDATE`, regardless of any other match.
  Agents may be candidates for deciding and interpreting; committing
  the result stays deterministic. No v1 agentic rule targets write
  steps, so this is a standing constraint on future rules, not an
  active tiebreaker.

Every stage except `start`, `end`, and `note` appears in exactly one
finding. Precedence resolves multiple matches; within one
classification, the lowest-numbered matching rule claims the stage.
This coverage invariant is tested: a stage the analyzer silently skips
is a bug, not a gap.

## Keep deterministic (KD rules)

- **KD-1. Calculation and data staging.** Calculation stages:
  arithmetic, field mapping, counters. Deterministic math must stay
  deterministic, especially where the numbers are regulated amounts (a
  fee formula is a contract term, not a judgment call).
  *Detector: stage type `calculation`.*
- **KD-2. Defined interface invocation.** Action stages that call a
  named object action, and subprocess calls. These are integrations
  against defined interfaces; the target system's contract does not
  get looser because a model is upstream. Write-shaped invocations are
  additionally protected by P-3.
  *Detector: stage types `action` and `subprocess_call`.*
- **KD-3. Queue mechanics.** Getting the next item, adding items,
  marking completion. These are platform primitives that map directly
  to UiPath Orchestrator queue operations.
  *Detector: stage types `queue_read` and `queue_write`, except
  exception dispositions, which HG-2 claims.*
- **KD-4. Explicit flow control.** Decision stages whose condition is
  an explicit boolean expression over defined data, and loops over
  declared collections. The logic is fully stated in the source; there
  is no judgment to uplift.
  *Detector: stage types `decision`, `loop_start`, `loop_end`.*
- **KD-5. Exception and retry geometry.** Blocks, recover and resume
  stages, and system exception throws. This is the machinery that
  becomes REFramework retry configuration; it must remain exact.
  *Detector: stage types `block`, `recover`, `resume`, and `exception`
  stages that are not business exceptions.*

## Agentic candidate (AC rules)

- **AC-1. Exact-match reconciliation.** A decision that matches
  records across data sources by exact equality on selected fields.
  Exact matching is how 2015 automation approximated the judgment
  "are these the same transaction"; it is brittle against date
  offsets, partial amounts, and formatting drift, and every near-miss
  becomes an exception a human untangles. Candidate design: agentic
  matching proposes, deterministic rules dispose (auto-accept exact
  matches, escalate everything else with the agent's reasoning
  attached).
  *Detector: decision stage whose expression equality-compares at
  least one collection field reference (`[Collection.Field]`) against
  another data reference.*
- **AC-2. Unstructured input interpretation.** A step that extracts
  meaning from free text, documents, or images before structured
  processing can start. This is the strongest agentic candidate class
  and the reason many processes were never automated end to end.
  *Detector: none in v1. The estate model does not yet carry enough
  signal to find these automatically; the rule exists so reviewers
  have an ID to cite when they spot one. Stated honestly: the
  analyzer will not emit AC-2 findings yet.*
- **AC-3. Threshold-only triage into a human gate.** A decision that
  routes work to human review using a single configured threshold.
  The threshold is a proxy for "is this case risky enough to need a
  person"; it was the best available encoding of that judgment in a
  deterministic tool. Candidate design: agent-assisted triage that
  may narrow, never widen, the set auto-processed below the gate; the
  human gate itself is preserved (P-2 keeps the gate stages
  `HUMAN_GATE`).
  *Detector: decision stage whose expression compares a data item
  against a configuration constant, where at least one directly
  linked successor stage is classified `HUMAN_GATE`. A configuration
  constant is a data item with a non-empty initial value that no
  stage in the process writes.*

## Human gate (HG rules)

- **HG-1. Spec-identified human touchpoints.** Stages the reviewed
  intent spec cites as human touchpoints, where the stage itself
  hands work over: creating a case for a reviewer, deferring an item
  pending a decision, recording an exception for investigation. The
  intent spec is the reviewed statement of where humans sit in the
  process; the analyzer treats it as authoritative.
  *Detector: stage cited by a `human_touchpoints` entry in the intent
  spec, with stage type `action`, `queue_write`, or `exception`.
  Cited decision stages are evidence of the routing, not the handoff
  itself, and remain eligible for AC-3 and KD-4.*
- **HG-2. Exception dispositions.** Marking a queue item as an
  exception, and throwing a business exception. Both end automated
  handling and leave the item in a state that implies a person
  investigates, whether or not the spec named the touchpoint.
  *Detector: `queue_write` stage whose action is an exception
  disposition, and `exception` stage whose type is a business
  exception.*

## Finding shape

One finding covers one step or step group with a shared rationale: one
HG-1 finding per spec touchpoint, one AC finding per matched decision,
one KD finding per rule across the stages it claims. Every finding
carries the stage IDs it covers, the rule IDs it rests on, and
reasoning written against the specific stages, not boilerplate. The
report records the spec it was analyzed against and that spec's status
at analysis time; a report over a draft spec says so.

## What v1 does not do

- It does not detect AC-2 (unstructured input) at all.
- It reads structure, not meaning: a judgment call hidden inside a
  code stage or an external system is invisible to it.
- It does not weigh value or volume; a finding says a step is a
  candidate, not that pursuing it is worth the effort. Prioritization
  needs the complexity scores and, later, run data the estate model
  does not contain.
- Its detectors are heuristics over stage shapes and expressions.
  They are tested against the fixture estate; a real estate will
  produce misses and false positives, and the findings are inputs to
  a human design review, not decisions.
