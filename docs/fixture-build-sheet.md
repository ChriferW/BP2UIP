# Meridian Estate: Fixture Build Sheet

Everything needed to author the fixture estate in one Blue Prism
session (Parallels, roadmap week 1). The design work is done here on
paper; the session should be mechanical clicking.

The plan: **author 4 processes, 2 objects, and 3 queues by hand**, then
export. The remaining 3 to 4 processes are derived afterward by editing
the exported XML, which the roadmap explicitly allows. For that to be
honest, one rule governs what must be hand-authored:

**Coverage rule: the authored set must contain at least one real
instance of every stage type and queue operation the estate uses.**
Derived processes only recombine XML element types that already exist
in a real export; they never introduce a guessed one.

The build log will state plainly which processes were authored and
which were derived.

---

## 1. Session order of work

1. Create the three work queues
2. Build the two objects (internals are minimal; see note below)
3. Build processes P03, P06, P01, P04 (simplest first, warms up muscle
   memory before the big one)
4. Create the release, export, sanity-check the XML in a text editor
   before closing Parallels

Note on object internals: no real target applications exist. Object
actions only need plausible structure (inputs, outputs, a calculation
or two, maybe a note stage). The fixtures exist to exercise the parser,
not to run.

## 2. Naming conventions

- Processes: `MFG - <Name>` (Meridian Financial Group)
- Objects: `MFG <System>`
- Queues: `Q-<Name>`
- Data items: PascalCase (`DisputeAmount`)
- Stage names: short verb phrases (`Lookup Account`, `Post Adjustment`).
  Stage names become citation targets in intent specs later; make them
  say what the stage does.

## 3. Work queues

| Queue | Key field | Used by |
|---|---|---|
| Q-Disputes | DisputeRef | P01 (read), P06 (write) |
| Q-PaymentInvestigations | PaymentRef | P02 derived (read) |
| Q-AccountMaintenance | RequestRef | P08 derived (write) |

## 4. Objects

### O1: MFG Core Banking

| Action | Inputs | Outputs | Internals |
|---|---|---|---|
| Lookup Account | AccountNumber (Text) | AccountStatus (Text), CustomerName (Text) | calculation setting outputs to fixed values |
| Get Transactions | AccountNumber (Text), FromDate (Date) | Transactions (Collection: TxnRef, Amount, TxnDate) | calculation stages building a 2 to 3 row collection |
| Post Adjustment | AccountNumber (Text), Amount (Number), Reason (Text) | AdjustmentRef (Text) | calculation setting AdjustmentRef |
| Update Account Status | AccountNumber (Text), NewStatus (Text) | Success (Flag) | calculation setting Success = True |

### O2: MFG Case Manager

| Action | Inputs | Outputs | Internals |
|---|---|---|---|
| Create Case | CaseType (Text), Reference (Text), Details (Text) | CaseId (Text) | calculation setting CaseId |
| Close Case | CaseId (Text), Outcome (Text) | Success (Flag) | calculation setting Success = True |

## 5. Authored processes

### P03: MFG - Address Change (author) — complexity: low

The baseline fixture: the simplest thing the parser must handle.

Purpose: apply a customer address change after checking the account.

Data items: AccountNumber (Text), NewAddress (Text), AccountStatus
(Text), CustomerName (Text), Success (Flag).

Flow:

1. Start (inputs: AccountNumber, NewAddress)
2. Note "Address changes require an active account" (note stage)
3. Action `Lookup Account` (O1: Lookup Account)
4. Decision `Account Active?` — expression `[AccountStatus] = "Active"`
   - No: Exception stage `Throw Inactive Account` (type: Business
     Exception, detail "Account not active")
5. Action `Update Account Status` (O1: Update Account Status, reusing
   the action as a stand-in update call)
6. End (output: Success)

Features exercised: sub-object call, single decision, exception throw,
note stage, process inputs/outputs.

### P06: MFG - Dispute Feeder (author) — complexity: low

Small on purpose: it exists to capture the Add To Queue XML for real
(P01 only reads the queue).

Purpose: load incoming disputes into Q-Disputes.

Data items: Disputes (Collection: DisputeRef, AccountNumber,
DisputeAmount, TransactionDate), ItemCount (Number).

Flow:

1. Start
2. Calculation stages building 3 rows into `Disputes` (or a collection
   with initial values; whichever is faster in the session)
3. Loop `For Each Dispute` over `Disputes` (loop start)
4. Action `Add Dispute To Queue` (Internal - Work Queues: Add To Queue,
   queue Q-Disputes, key `[Disputes.DisputeRef]`)
5. Calculation `Count Loaded` — `[ItemCount] + 1` into ItemCount
6. Loop end
7. End (output: ItemCount)

Features exercised: collection loop, queue write, calculation.

### P01: MFG - Card Dispute Intake (author) — complexity: medium

The flagship fixture: this is the roadmap's "at least one process
with a decision tree, a calculation block, a loop, an exception block,
a sub-object call, and a queue interaction," all in one process. Budget
the most session time here.

Purpose: work dispute items from Q-Disputes; verify the account and
the disputed transaction, compute provisional credit, post it, route
big or failed items to a human case.

Data items: DisputeRef (Text), AccountNumber (Text), DisputeAmount
(Number), TransactionDate (Date), AccountStatus (Text), CustomerName
(Text), Transactions (Collection), TransactionFound (Flag),
ProvisionalCredit (Number), FeeRefund (Number), RetryCount (Number,
initial 0), CaseId (Text).

Constants to keep visible (data items with initial values, so the
intent extractor has business rules to find): ReviewThreshold (Number,
500), FeeRate (Number, 0.015), MaxPostAttempts (Number, 3).

Flow:

1. Start
2. Action `Get Next Dispute` (Internal - Work Queues: Get Next Item,
   Q-Disputes; outputs into DisputeRef, AccountNumber, DisputeAmount,
   TransactionDate)
3. Decision `Item Retrieved?` — No: End `No More Items`
4. Action `Lookup Account` (O1: Lookup Account)
5. Decision `Account Active?` — `[AccountStatus] = "Active"`
   - No: Action `Mark Exception - Inactive Account` (Work Queues: Mark
     Exception), link back to `Get Next Dispute`
6. Action `Get Transactions` (O1: Get Transactions)
7. Loop `For Each Transaction` over Transactions:
   - Decision `Matches Disputed Transaction?` —
     `[Transactions.TxnDate] = [TransactionDate] AND
     [Transactions.Amount] = [DisputeAmount]`
     - Yes: Calculation `Flag Transaction Found` — True into
       TransactionFound
8. Decision `Transaction Found?`
   - No: Action `Mark Exception - No Matching Transaction` (Mark
     Exception), link back to `Get Next Dispute`
9. Decision `Amount Over Review Threshold?` —
   `[DisputeAmount] > [ReviewThreshold]`
   - Yes: Action `Create Review Case` (O2: Create Case) then Action
     `Defer For Review` (Work Queues: Mark Exception with "manual
     review" reason, or Defer; whichever is quicker), link back to
     `Get Next Dispute`
10. Calculation `Compute Fee Refund` —
    `[DisputeAmount] * [FeeRate]` into FeeRefund
11. Calculation `Compute Provisional Credit` —
    `[DisputeAmount] + [FeeRefund]` into ProvisionalCredit
12. Recover stage `Catch Posting Failure` opening the exception block
    around the posting call:
    - Action `Post Adjustment` (O1: Post Adjustment, amount
      ProvisionalCredit)
    - On exception: Calculation `Increment Retry` — `[RetryCount] + 1`
      into RetryCount; Decision `Retry Limit Reached?` —
      `[RetryCount] >= [MaxPostAttempts]`
      - No: Resume stage, link back to `Post Adjustment`
      - Yes: Action `Mark Exception - Posting Failed` (Mark Exception),
        link back to `Get Next Dispute`
13. Action `Mark Dispute Complete` (Work Queues: Mark Completed)
14. Link back to `Get Next Dispute` (the main work loop)

Features exercised: queue read/complete/exception, chained decision
tree (steps 3, 5, 8, 9), collection loop, calculation block (two
chained calcs), recover/resume exception block with a retry loop, two
different sub-object calls.

### P04: MFG - Daily Settlement Reconciliation (author) — complexity: medium

Purpose: total the day's settlement rows and raise a variance
exception when the total drifts from the expected figure.

Data items: ReportRows (Collection: RowRef, Amount), RunningTotal
(Number, initial 0), ExpectedTotal (Number), Variance (Number),
Tolerance (Number, initial 25), RowCount (Number, initial 0), CaseId
(Text).

Flow:

1. Start (input: ExpectedTotal)
2. Action `Get Transactions` (O1: Get Transactions, standing in as the
   report source; outputs into ReportRows)
3. Loop `For Each Row` over ReportRows:
   - Calculation `Accumulate Total` — `[RunningTotal] +
     [ReportRows.Amount]` into RunningTotal
   - Calculation `Count Rows` — `[RowCount] + 1` into RowCount
4. Calculation `Compute Variance` —
   `[RunningTotal] - [ExpectedTotal]` into Variance
5. Decision `Variance Within Tolerance?` —
   `[Variance] <= [Tolerance] AND [Variance] >= 0 - [Tolerance]`
   - No: Action `Create Variance Case` (O2: Create Case), then
     Exception stage `Throw Variance Exception` (Business Exception)
6. End (outputs: RunningTotal, RowCount)

Features exercised: loop with multi-calculation body, arithmetic
decision, sub-object call, exception throw.

## 6. Derived processes (built later by editing exported XML)

These reuse only element types the authored four already contain.
Outlines here so the estate reads as one coherent bank back office.

### P02: MFG - Payment Investigation — complexity: high (derived from P01)

Works Q-PaymentInvestigations. Same skeleton as P01 with a deeper
decision tree: payment channel (wire / ACH / internal) branches to
different evidence checks; adds a second collection loop over account
history; refund calculation uses a channel-dependent fee. The most
complex process in the estate; exists to stretch complexity scoring.

### P05: MFG - Dormant Account Review — complexity: low-medium (derived from P03)

Startup-parameter driven. Chained decisions on last-activity date,
balance, and account type decide close / warn / leave; one sub-object
call per outcome. Decision-tree heavy with no loop, so the analyzer
has a judgment-shaped candidate (dormancy exceptions) to classify.

### P07: MFG - Chargeback Escalation — complexity: medium (derived from P01)

The P01 review-threshold branch expanded into its own process: takes
deferred disputes, creates and tracks a case, closes it with an
outcome. Human touchpoints on both ends; exists to give the intent
extractor and uplift analyzer a HUMAN GATE shaped fixture.

### P08 (optional, if time): MFG - Standing Order Amendment — complexity: low (derived from P03/P06)

Address-change skeleton plus an Add To Queue write to
Q-AccountMaintenance. Brings the estate to 8 processes.

## 7. Feature coverage matrix

| Feature | P01 | P02 | P03 | P04 | P05 | P06 | P07 |
|---|---|---|---|---|---|---|---|
| Decision tree (chained decisions) | x | x |  |  | x |  | x |
| Calculation block | x | x |  | x |  | x |  |
| Collection loop | x | x |  | x |  | x |  |
| Exception block (recover/resume) | x | x |  |  |  |  | x |
| Exception throw stage |  |  | x | x |  |  |  |
| Sub-object call | x | x | x | x | x |  | x |
| Queue read / complete / mark exception | x | x |  |  |  |  | x |
| Queue write (Add To Queue) |  |  |  |  |  | x |  |
| Note stage |  |  | x |  |  |  |  |

Authored: P01, P03, P04, P06 (bold requirement: these four alone cover
every row above). Derived: P02, P05, P07, P08.

## 8. Export checklist (before closing Parallels)

1. Create a release named `Meridian Legacy Estate` containing all
   processes, both objects, and all three queues; export as
   `meridian-estate.bprelease`
2. Also export one release per authored process (process plus the
   objects and queues it references), named
   `meridian-p01-dispute-intake.bprelease`,
   `meridian-p03-address-change.bprelease`,
   `meridian-p04-reconciliation.bprelease`,
   `meridian-p06-dispute-feeder.bprelease`
3. Open each file in a text editor and confirm it is XML with the
   process definitions embedded, not an empty wrapper
4. Note the exact Blue Prism version for the week 1 build-log entry
5. Copy everything out of the VM, commit to `fixtures/`

Step 2 matters because parser unit tests key on per-fixture files, and
a single-process release is the honest sample for deriving P02, P05,
P07, and P08.
