"""Analysis layer tests: complexity, dependency graph, and the uplift
analyzer against docs/uplift-criteria.md. The criteria document is the
contract; a test at the bottom asserts every rule ID the analyzer emits
exists in the document."""

import re
from pathlib import Path

import pytest

from bp2uip.analysis import (
    CRITERIA_VERSION,
    analyze_uplift,
    build_dependency_graph,
    score_complexity,
)
from bp2uip.model import (
    Estate,
    EstateRef,
    Extraction,
    HumanTouchpoint,
    IntentSpec,
    Process,
    PurposeSection,
    utc_now,
)

CRITERIA_DOC = Path(__file__).resolve().parents[2] / "docs" / "uplift-criteria.md"


def _process(estate: Estate, name: str) -> Process:
    return next(p for p in estate.processes if p.name == name)


def _stage_id(process: Process, name: str) -> str:
    return next(s.id for s in process.stages if s.name == name)


def _spec_for(process: Process, touchpoints: list[tuple[str, list[str]]]) -> IntentSpec:
    """A minimal spec for a parsed process; touchpoints are
    (description, [stage names]) pairs."""
    return IntentSpec(
        spec_id=f"spec-{process.id}",
        process_id=process.id,
        estate_ref=EstateRef(path="artifacts/estate/estate.json", sha256="0" * 64),
        status="draft",
        created_at=utc_now(),
        extraction=Extraction(provider="fake", model="fake-model", prompt_version="0.1.0"),
        purpose=PurposeSection(text="Test.", citations=[process.stages[0].id]),
        inputs=[],
        outputs=[],
        business_rules=[],
        exception_semantics=[],
        human_touchpoints=[
            HumanTouchpoint(
                description=description,
                citations=[_stage_id(process, n) for n in names],
            )
            for description, names in touchpoints
        ],
        approval=None,
    )


@pytest.fixture(scope="module")
def p01(full_estate) -> Process:
    return _process(full_estate, "MFG - Card Dispute Intake")


@pytest.fixture(scope="module")
def p01_report(full_estate, p01):
    spec = _spec_for(
        p01,
        [
            (
                "High-value disputes are routed to a human reviewer.",
                ["Amount Over Review Threshold?", "Create Review Case", "Defer For Review"],
            )
        ],
    )
    return analyze_uplift(full_estate, spec)


# --------------------------------------------------------------------------
# Complexity
# --------------------------------------------------------------------------


def test_complexity_dimensions_for_dispute_intake(full_estate):
    scores = {s.process_name: s for s in score_complexity(full_estate)}
    intake = scores["MFG - Card Dispute Intake"]
    assert intake.stage_count == 29
    assert intake.logic_stage_count == 27
    assert intake.decision_count == 6
    assert intake.loop_count == 1
    assert intake.object_call_count == 4
    assert intake.distinct_objects == ["MFG Case Manager", "MFG Core Banking"]
    assert intake.queue_operation_count == 6
    # block + recover + 2 resumes + 1 declared exception block
    assert intake.exception_construct_count == 5
    assert intake.band == "high"


def test_branching_depth_counts_decisions_on_longest_path(full_estate):
    scores = {s.process_name: s for s in score_complexity(full_estate)}
    # Item Retrieved?, Account Active?, Matches Disputed Transaction?,
    # Transaction Found?, Amount Over Review Threshold? lie on one path.
    assert scores["MFG - Card Dispute Intake"].branching_depth == 5
    assert scores["MFG - Dispute Feeder"].branching_depth == 0


def test_bands_spread_across_the_estate(full_estate):
    bands = {s.process_name: s.band for s in score_complexity(full_estate)}
    assert bands["MFG - Card Dispute Intake"] == "high"
    assert bands["MFG - Address Change"] == "low"
    assert bands["MFG - Dispute Feeder"] == "low"


# --------------------------------------------------------------------------
# Dependency graph
# --------------------------------------------------------------------------


def test_object_dependencies_and_fan_in(full_estate):
    graph = build_dependency_graph(full_estate)
    intake = next(p for p in graph.processes if p.process_name == "MFG - Card Dispute Intake")
    core = next(o for o in intake.objects if o.object == "MFG Core Banking")
    assert core.actions == ["Get Transactions", "Lookup Account", "Post Adjustment"]
    fan_in = next(f for f in graph.object_fan_in if f.object == "MFG Core Banking")
    address = _process(full_estate, "MFG - Address Change")
    dispute = _process(full_estate, "MFG - Card Dispute Intake")
    assert set(fan_in.used_by) >= {address.id, dispute.id}


def test_queue_operations_attributed_to_single_read_queue(full_estate):
    graph = build_dependency_graph(full_estate)
    intake = next(p for p in graph.processes if p.process_name == "MFG - Card Dispute Intake")
    disputes = next(q for q in intake.queues if q.queue == "Q-Disputes")
    # One named read; the four exception marks and one completion name
    # no queue and are attributed to the only queue the process reads.
    assert disputes.reads == 1
    assert disputes.adds == 0
    assert disputes.dispositions == 5


def test_queue_coupling_derives_producer_consumer_edge(full_estate):
    graph = build_dependency_graph(full_estate)
    coupling = next(c for c in graph.queue_couplings if c.queue == "Q-Disputes")
    feeder = _process(full_estate, "MFG - Dispute Feeder")
    intake = _process(full_estate, "MFG - Card Dispute Intake")
    assert coupling.producers == [feeder.id]
    assert coupling.consumers == [intake.id]


# --------------------------------------------------------------------------
# Uplift analyzer
# --------------------------------------------------------------------------


def _finding_for(report, stage_id):
    return next(f for f in report.findings if stage_id in f.stage_ids)


def test_every_behavioral_stage_lands_in_exactly_one_finding(p01, p01_report):
    structural = {s.id for s in p01.stages if s.type in ("start", "end", "note")}
    seen: list[str] = []
    for finding in p01_report.findings:
        seen.extend(finding.stage_ids)
    assert len(seen) == len(set(seen)), "a stage appears in two findings"
    assert set(seen) == {s.id for s in p01.stages} - structural


def test_spec_touchpoint_handoffs_become_human_gates(p01, p01_report):
    case = _finding_for(p01_report, _stage_id(p01, "Create Review Case"))
    assert case.classification == "HUMAN_GATE"
    assert case.criteria == ["HG-1"]
    assert _stage_id(p01, "Defer For Review") in case.stage_ids
    # The cited decision stage is routing evidence, not the handoff.
    assert _stage_id(p01, "Amount Over Review Threshold?") not in case.stage_ids


def test_unnamed_exception_dispositions_become_human_gates(p01, p01_report):
    finding = _finding_for(p01_report, _stage_id(p01, "Mark Exception - Inactive Account"))
    assert finding.classification == "HUMAN_GATE"
    assert finding.criteria == ["HG-2"]
    assert _stage_id(p01, "Mark Exception - Posting Failed") in finding.stage_ids


def test_exact_match_reconciliation_is_agentic_candidate(p01, p01_report):
    finding = _finding_for(p01_report, _stage_id(p01, "Matches Disputed Transaction?"))
    assert finding.classification == "AGENTIC_CANDIDATE"
    assert finding.criteria == ["AC-1"]
    assert "Transactions.TxnDate" in finding.reasoning


def test_threshold_triage_into_human_gate_is_agentic_candidate(p01, p01_report):
    finding = _finding_for(p01_report, _stage_id(p01, "Amount Over Review Threshold?"))
    assert finding.classification == "AGENTIC_CANDIDATE"
    assert "AC-3" in finding.criteria
    assert "ReviewThreshold" in finding.reasoning


def test_retry_limit_decision_stays_deterministic(p01, p01_report):
    # Compares against configuration (MaxPostAttempts) but routes to
    # resume stages, not a human gate, so AC-3 must not fire.
    finding = _finding_for(p01_report, _stage_id(p01, "Retry Limit Reached?"))
    assert finding.classification == "KEEP_DETERMINISTIC"
    assert finding.criteria == ["KD-4"]


def test_money_writes_stay_deterministic(p01, p01_report):
    finding = _finding_for(p01_report, _stage_id(p01, "Post Adjustment"))
    assert finding.classification == "KEEP_DETERMINISTIC"
    assert finding.criteria == ["KD-2"]


def test_business_exception_is_human_gate_without_spec_touchpoints(p03_estate):
    process = p03_estate.processes[0]
    report = analyze_uplift(p03_estate, _spec_for(process, []))
    finding = _finding_for(report, _stage_id(process, "Throw Inactive Account"))
    assert finding.classification == "HUMAN_GATE"
    assert finding.criteria == ["HG-2"]


def test_report_records_spec_status_and_criteria_version(p01_report):
    assert p01_report.spec_ref.status_at_analysis == "draft"
    assert p01_report.criteria_version == CRITERIA_VERSION


def test_unknown_process_raises(full_estate, p01):
    spec = _spec_for(p01, [])
    spec = spec.model_copy(update={"process_id": "proc-nonexistent"})
    with pytest.raises(ValueError, match="not in the estate"):
        analyze_uplift(full_estate, spec)


# --------------------------------------------------------------------------
# Contract with docs/uplift-criteria.md
# --------------------------------------------------------------------------


def test_every_emitted_criteria_id_exists_in_the_document(full_estate, p01_report, p03_estate):
    doc = CRITERIA_DOC.read_text(encoding="utf-8")
    documented = set(re.findall(r"\*\*((?:P|KD|AC|HG)-\d+)", doc))
    p03_report = analyze_uplift(p03_estate, _spec_for(p03_estate.processes[0], []))
    emitted = {
        rule
        for report in (p01_report, p03_report)
        for finding in report.findings
        for rule in finding.criteria
    }
    assert emitted, "the analyzer emitted no criteria at all"
    assert emitted <= documented, f"undocumented rule ids: {emitted - documented}"


def test_criteria_version_matches_the_document(full_estate):
    doc = CRITERIA_DOC.read_text(encoding="utf-8")
    assert f"Criteria version {CRITERIA_VERSION}." in doc
