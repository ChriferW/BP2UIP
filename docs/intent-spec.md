# The intent spec

The intent spec is the project's intermediate representation: the
business intent of one Blue Prism process, extracted from the parsed
estate, expressed as claims a reviewer can check. It is the artifact
the whole pipeline pivots on. Everything upstream (parsing) exists to
produce it; everything downstream (PDD, SDD, UiPath artifacts) is
generated from it, and only after a person approves it.

The machine-readable definition is `schema/intent-spec.schema.json`,
mirrored by the `IntentSpec` model in `pipeline/src/bp2uip/model.py`.
A contract test keeps the two in agreement. This document explains the
format and the rules around it.

## Why intent, not structure

The .bprelease XML records how a process works: stages, links,
expressions. It does not record why. A migration that copies structure
reproduces ten years of workarounds on a new platform. The intent spec
states what the process is for, what it consumes and produces, which
rules it enforces, and what it does when things go wrong, so that the
regenerated artifacts can serve the intent rather than mimic the
mechanics.

## The citation rule

Every claim in a spec must cite at least one stage id from the estate
document it was extracted from. This is the anti-hallucination
mechanism: an LLM drafts the spec, and an LLM will happily assert
things the source does not support. A claim with no citation, or a
citation naming a stage that does not exist, fails validation
(`intent.validate_spec`) and the spec is rejected. During review, the
citations are what let a human check each claim against the source.

## Sections

A spec has six content sections. All of them carry citations.

| Section | What it states |
|---|---|
| `purpose` | One paragraph: what the process achieves and why it exists |
| `inputs` | What the process consumes, and where each input comes from |
| `outputs` | What the process produces, and where each output goes |
| `business_rules` | The rules the process enforces, numbered BR-1, BR-2, ... |
| `exception_semantics` | What can go wrong and what the process currently does about it |
| `human_touchpoints` | Where a person is, or should be, involved |

An empty list is a valid value for every section except `purpose`: a
process with no human touchpoints has an empty `human_touchpoints`,
not an invented one.

## Metadata

Every spec records where it came from:

- `spec_id` and `process_id` tie the spec to one process in the estate.
- `estate_ref` is the path and sha256 of the exact estate document the
  spec was extracted from. If the estate is re-parsed, the hash no
  longer matches and the spec is visibly stale.
- `extraction` records the provider name, the exact model string the
  API served, and the prompt version (`intent.PROMPT_VERSION`, bumped
  whenever the prompt text changes). A spec can always be traced to
  the prompt and model that drafted it. Credentials are never recorded.

## Lifecycle

A spec is `draft` or `approved`, and the transition is one-way.

- Extraction always produces a draft. No exceptions.
- `approve_spec` (CLI: `bp2uip review <spec> --approve --by <name>`)
  is the only path to approved. It requires a reviewer identity, which
  is never inferred from git config or the environment, and it records
  a `spec_approved` event in the process provenance log, including any
  corrections the reviewer made.
- The schema enforces the pairing both ways: an approved spec must
  carry an approval record, a draft must not.
- Nothing downstream runs on a draft. Generation from an unapproved
  spec requires `--force` and is recorded in provenance as an
  unreviewed generation.

## How a spec is produced

`intent.extract_intent` serializes one process, plus the objects and
work queues its stages reference, into a versioned prompt. The
provider returns JSON with the six sections; the pipeline supplies all
metadata itself. The response is validated twice: shape (the Pydantic
model) and citations (`validate_spec`). If either fails, the provider
gets its rejected output back with the reasons and one chance to
correct it; a second failure aborts the extraction with an error. The
retry exists because model output is not deterministic, and the hard
stop exists because silently accepting bad output would defeat the
point.

## Designed for week 5

The sections are chosen so that document generation is a mapping, not
another extraction: `purpose` and `inputs`/`outputs` seed the PDD
overview, `business_rules` become the PDD rules table and the SDD
validation logic, `exception_semantics` drive the REFramework
exception configuration, and `human_touchpoints` mark the boundaries
that stay manual (or become agent handoffs) in the to-be design. If a
section proves too thin to generate from, the fix is to enrich this
format, not to invent content downstream.
