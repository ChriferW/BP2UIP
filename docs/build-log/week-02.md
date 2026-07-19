# Week 2: The parser

Date: 2026-07-18

## What happened

`bp2uip.parser` is implemented and the 7 skipped fixture-matrix tests
are now real, passing tests. `parse_release` reads one or more
.bprelease exports into the estate model: processes with stages,
data items, links, and resolved exception blocks; objects with their
published actions; queues with key field and max attempts. The
`bp2uip parse` CLI command writes `estate.json`, and that output
validates against `schema/estate.schema.json`.

Feature coverage, as required by the testing strategy in
docs/master-plan.md section 5:

| Fixture | Features exercised in tests |
|---|---|
| meridian-estate | whole estate, multi-file dedup, all of the below |
| meridian-p01-dispute-intake | calculation, multi calc, loop, exception block (Block/Recover/Resume), queue read, queue writes |
| meridian-p03-address-change | decision links and labels, sub-object call cross-reference, exception throw |
| meridian-p04-reconciliation | whole-estate sweep (loop and decision shapes shared with P01/P06) |
| meridian-p06-dispute-feeder | loop pairing and body membership, queue write with named queue |

Every fixture parses with zero entries in `unparsed`. The tests
deviate from the plan's "one test module per fixture file" in favor of
one module keyed by feature, matching the skipped placeholders
one-to-one; the table above is the per-fixture map.

Deliberately not modeled (the skip lists in `parser.py`, documented
here as the honesty contract requires): canvas chrome. `ProcessInfo`
and `SubSheetInfo` stages are the info boxes Blue Prism draws on every
page; `view`, `preconditions`, `endpoint`, `appdef` carry no process
behavior; release-level `process-group`/`object-group` entries mirror
the Studio tree folders. Objects' Initialise and Clean Up lifecycle
pages are skipped because the fixtures leave them untouched. None of
these appear in `unparsed` because skipping them is a decision, not a
gap.

## What broke or surprised me

- The components inside a release's `contents` element each live in
  their own XML namespace (process, object, work-queue), not the
  release namespace. The first parser draft matched on the wrong
  namespace and parsed an empty estate; 12 failing tests caught it
  immediately.
- A Block stage in the export is nothing but a rectangle: display x/y
  (top left) and w/h. Which stages it covers, and therefore which
  Recover stage handles exceptions, is pure geometry. The parser
  resolves coverage by point-in-rectangle containment, which felt
  wrong until the fixture confirmed there is simply nothing else in
  the XML to go on.
- P06 contains a stage named "Stage Dsipute Row", a genuine typo from
  the authoring session. It stays: legacy estates contain typos and
  the parser must not care. The test asserts the misspelled name.
- Links are not a separate element; they hang off each stage as
  `onsuccess`/`ontrue`/`onfalse` children holding the target stage id.
- The venv's hidden-flag problem recurred twice in one session, so
  pytest now sets `pythonpath = ["src"]` and no longer depends on the
  editable install's .pth file.

## Decisions made

- StageType gains `block`, `recover`, `resume`, and `data`; Queue
  gains `key_field` and `max_attempts`. Additive, mirrored in the
  JSON Schema, and the contract tests keep both in agreement. The
  retry semantics and queue corroboration are exactly what week 3's
  intent extractor needs.
- Blue Prism's built-in Work Queues object maps to `queue_read` /
  `queue_write` stage types, with the queue name extracted from the
  action's inputs; queue actions the fixtures do not use fall back to
  plain `action`.
- Multi-file parses deduplicate shared components by Blue Prism id,
  first occurrence wins, so the estate file plus per-process files can
  be parsed together without double counting.

## Next

Week 3: the intent extractor. `extract_intent` reads a process from
this estate model and drafts an intent spec through the provider
interface, with every claim citing stage ids the parser now supplies.
