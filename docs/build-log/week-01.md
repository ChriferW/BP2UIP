# Week 1: Authoring the Meridian estate in Blue Prism

Date: 2026-07-18

## What happened

The synthetic source estate now exists. Working in Blue Prism v7.5.1
inside a Parallels VM, I authored by hand:

- 3 work queues (Q-Disputes, Q-PaymentInvestigations,
  Q-AccountMaintenance), each with Maximum Attempts set to 3
- 2 business objects (MFG Core Banking with 4 published actions, MFG
  Case Manager with 2), all returning hard-coded values
- 4 processes: P01 Card Dispute Intake (queue-driven, with a
  Block/Recover/Resume retry section), P03 Address Change, P04 Daily
  Settlement Reconciliation, and P06 Dispute Feeder

Everything validated clean, then went out through the Releases tab as
5 .bprelease exports: one full-estate file and one per process. The
files were sanity-checked programmatically (correct components in
each, retry constructs and business expressions present in P01, queue
config carrying max-attempts="3") and now live in fixtures/.

To be clear about provenance: these four processes are the authored
set. The remaining processes in the estate design (P02, P05, P07,
P08) will be derived later by editing copies of this exported XML on
the Mac, no Blue Prism involved. The whole estate is fictional, the
objects are stubs that never touch a real application, and nothing in
fixtures/ has ever been run as an automation. The fixtures exist to
be parsed, not executed.

## What broke or surprised me

I had never used Blue Prism before this week, and it showed:

- Object actions are invisible to processes until each page is
  explicitly published (Page Properties > Publish this Action). I
  built an entire object and then could not call it, and the Action
  dropdown gives no hint about why it is empty.
- Blue Prism validation would not accept the retry give-up path until
  a Resume stage sat between the retry-limit decision and the Mark
  Exception action. The error "Recovery stage is linked back to main
  process" is accurate but only makes sense after you know the rule:
  every route out of a Recover must pass through a Resume.
- Collection outputs are field-checked at validation time. P04's
  ReportRows collection had to adopt the exact field names of the Get
  Transactions output (TxnRef, Amount, TxnDate) before the process
  would validate.
- Add To Queue has no Key input. The queue's own Key Name setting
  pulls the key out of the item data, which is tidier than the build
  sheet assumed. It also wants its Data input as a collection, so P06
  stages each row through a single-row staging collection.
- On the Mac side, the pipeline venv broke again with the known
  hidden .pth issue. The durable fix is
  `chflags -R nohidden pipeline/.venv`; unhiding just the .pth file
  did not stick.

## Decisions made

- Queue Maximum Attempts is 3, not the default 1, so the exported
  queue config corroborates P01's retry logic instead of
  contradicting it.
- P04 reuses Get Transactions as its report source rather than adding
  a new object action. The estate stays small and the parser still
  sees a realistic action call.
- P01's manual-review path uses Mark Exception with a "Deferred for
  manual review" reason rather than the Defer action, which wants a
  DateTime and adds nothing the intent extractor needs.

## Next

Week 2 starts on the parser: the 7 skipped tests in
tests/test_parser.py run against these fixtures.
