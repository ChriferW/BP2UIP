# Week 3: The IR

Date: 2026-07-20

## What happened

The design bet is real. `extract_intent` serializes one process plus
the objects and queues it references into a versioned prompt, sends it
through the provider interface (Anthropic implemented, key loaded from
a gitignored .env), and validates the response twice: shape against
the Pydantic model, citations against the estate. Invalid output goes
back to the provider with the reasons for exactly one retry; a second
failure aborts. The CLI `extract` and `review` commands are live, each
writing provenance events, and the spec format is documented in
docs/intent-spec.md.

Three processes were extracted against the real API (claude-sonnet-5,
prompt v0.1.0), reviewed, and approved with a named human on the
provenance chain: P01 Card Dispute Intake, P03 Address Change, and P06
Dispute Feeder. The specs live in artifacts/ next to the estate they
cite, each with a derived intent-spec.md rendering (render.py, a pure
mapping, no LLM) that resolves citation GUIDs to stage names so the
evidence is readable on GitHub. This week also added
docs/how-it-works.md, an end-to-end explainer of the pipeline.

## Where extraction was wrong

The section the roadmap demands. Prompt v0.1.0 held up better than
expected, but not perfectly:

- A pre-commit smoke run on P03 claimed the account status is set to
  "Updated", a misreading of the "Update Account Status" action name.
  The committed run, same prompt and model, did not repeat it. That is
  the nondeterminism argument for the review gate in one sentence: a
  spec is only as good as the run that produced it, so a human checks
  every claim against its citations before anything downstream runs.
- P06's input `source` field says the disputes collection is
  "presumably sourced upstream from a case management or transaction
  system". The citation rule polices stage ids, not prose, so hedged
  speculation can leak into free-text fields. Candidate fix for prompt
  v0.2; for now it is the reviewer's job to strike or accept it.
- The retry path never fired against the real API; all three runs
  produced valid, fully cited JSON on the first attempt. The retry is
  exercised by tests only. Honest status, and cheap insurance.

What it got right is worth recording too: P01's five business rules
including the fee formula and the retry-then-exception semantics read
from Block/Recover/Resume geometry, an implicit human touchpoint
(exceptioned queue items imply someone investigates), and BR-2 of P06,
which states its rule in clean language while citing the misspelled
"Stage Dsipute Row" stage. Reading through typos without repeating
them is exactly the behavior a legacy estate needs.

## What broke or surprised me

- The venv's hidden-flag problem took its third victim: the `bp2uip`
  console script. The pip-generated launcher relies on the .pth file
  that macOS keeps hiding, so the launcher itself is now patched
  locally to put src on sys.path. Machine-local, inside .venv, not
  committed; re-patch if the package is ever reinstalled.
- One approval session did not land: the specs still read draft
  afterward, most likely a path typo. The state on disk exposed it
  immediately, which is the point of checking the artifact rather than
  trusting the memory of having run a command.
- My own name confusion, not the model's: P01 is "MFG - Card Dispute
  Intake", not "MFG - Dispute Intake". The extract command's error
  message lists the estate's process names, which turned a mistake
  into a lookup.

## Decisions made

- API keys load from a gitignored .env at CLI startup via
  python-dotenv. The code still reads environment variables only; the
  file is just how the environment gets populated locally, and
  .env.example documents the variables without the secrets.
- The JSON spec is canonical; intent-spec.md is a derived view,
  regenerated on extract and on approve, never edited by hand. An
  unknown citation id renders verbatim instead of being hidden.
- Spec artifacts live in artifacts/<process-name-slug>/ alongside
  their provenance log.
- Do not re-parse the estate after extracting from it: parsing stamps
  a timestamp, which changes the file's sha256, which makes every
  spec's estate_ref visibly stale. That staleness is a feature, so the
  workflow is parse once, extract many.

## Next

Week 4: the analysis layer. Complexity and effort scoring, the
dependency graph, uplift analyzer v1 (docs/uplift-criteria.md first,
code implements the doc), and the dashboard scaffold that turns these
JSON artifacts into something navigable, starting with the spec
viewer the markdown rendering approximates today.
