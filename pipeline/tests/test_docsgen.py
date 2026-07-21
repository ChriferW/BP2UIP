"""Document generation tests: PDD, SDD, and the modernization report.
All generation is a pure mapping from the artifacts; these tests
assert the documents carry the source's facts with citations resolved,
and that the gate and provenance behavior holds end to end."""

import pytest

from bp2uip.analysis import analyze_uplift
from bp2uip.docsgen import (
    GenerationError,
    generate_pdd,
    generate_report,
    generate_sdd,
)
from bp2uip.intent import approve_spec
from bp2uip.model import Process
from bp2uip.provenance import ProvenanceLog
from conftest import make_spec, stage_id


def _process(estate, name: str) -> Process:
    return next(p for p in estate.processes if p.name == name)


@pytest.fixture
def p01(full_estate) -> Process:
    return _process(full_estate, "MFG - Card Dispute Intake")


@pytest.fixture
def log(tmp_path):
    return ProvenanceLog.open(tmp_path / "provenance.jsonl", "proc-test")


@pytest.fixture
def approved_p01(p01, log):
    spec = make_spec(
        p01,
        [
            (
                "High-value disputes go to a human reviewer.",
                ["Amount Over Review Threshold?", "Create Review Case", "Defer For Review"],
            )
        ],
    )
    return approve_spec(spec, approved_by="Test Reviewer", log=log)


def test_pdd_carries_the_facts_with_citations_resolved(
    full_estate, p01, approved_p01, log, tmp_path
):
    doc = generate_pdd(full_estate, approved_p01, log, out_dir=tmp_path)
    md = doc.markdown_path.read_text(encoding="utf-8")
    assert "# Process Definition Document (as-is): MFG - Card Dispute Intake" in md
    assert "Approved by: **Test Reviewer**" in md
    # Trigger derived from the queue read, with queue config from the estate.
    assert "Q-Disputes" in md
    assert "max 3 attempts" in md
    # Flow walk present, citations resolved to names not GUIDs.
    assert "## 5. Current-state flow" in md
    assert stage_id(p01, "Create Review Case") not in md
    # Configuration constants with their source values.
    assert "| ReviewThreshold | 500 |" in md
    # Structural exception handling.
    assert "an exception block covers" in md


def test_pdd_flow_walk_orders_true_branch_first(full_estate, approved_p01, log, tmp_path):
    md = generate_pdd(full_estate, approved_p01, log, out_dir=tmp_path).markdown_path.read_text(
        encoding="utf-8"
    )
    flow = md[md.index("## 5.") : md.index("## 6.")]
    # Item Retrieved? branches true to Unpack Dispute Item, false to the
    # end stage; the true branch reads first.
    assert flow.index("Unpack Dispute Item") < flow.index("No More Items")
    assert "exception recovery path" in flow


def test_pdd_appends_generation_event(full_estate, approved_p01, log, tmp_path):
    generate_pdd(full_estate, approved_p01, log, out_dir=tmp_path)
    events = [e.event for e in log.events()]
    assert events == ["spec_approved", "generation"]
    assert log.events()[-1].detail["kind"] == "pdd"


def test_pdd_force_on_draft_writes_doc_and_unreviewed_event(full_estate, p01, log, tmp_path):
    draft = make_spec(p01, [])
    doc = generate_pdd(full_estate, draft, log, out_dir=tmp_path, force=True)
    assert doc.markdown_path.exists()
    events = [e.event for e in log.events()]
    assert events == ["unreviewed_generation", "generation"]
    md = doc.markdown_path.read_text(encoding="utf-8")
    assert "force-generated from a draft" in md


def test_sdd_designs_from_spec_and_uplift(full_estate, p01, approved_p01, log, tmp_path):
    uplift = analyze_uplift(full_estate, approved_p01)
    doc = generate_sdd(full_estate, approved_p01, uplift, log, out_dir=tmp_path)
    md = doc.markdown_path.read_text(encoding="utf-8")
    assert "# Solution Design Document (to-be): MFG - Card Dispute Intake" in md
    # Architecture derived from queue usage.
    assert "performer" in md
    # Queue and config design carry source values.
    assert "| Q-Disputes | Orchestrator queue | DisputeRef | 3 |" in md
    assert "ReviewThreshold" in md
    # Exception taxonomy mapping covers the recovery block.
    assert "REFramework system-exception retry" in md
    # Uplift decisions and the human TODO list.
    assert "AGENTIC_CANDIDATE" in md
    assert "## 5. Human build TODO list" in md
    assert "MFG Core Banking" in md
    assert "Decide finding" in md


def test_sdd_rejects_mismatched_uplift_report(full_estate, approved_p01, log, tmp_path):
    other = _process(full_estate, "MFG - Dispute Feeder")
    wrong = analyze_uplift(full_estate, make_spec(other, []))
    with pytest.raises(GenerationError, match="uplift report is for process"):
        generate_sdd(full_estate, approved_p01, wrong, log, out_dir=tmp_path)


def test_report_orders_waves_and_holds_coupled_processes_together(full_estate, tmp_path):
    specs = [make_spec(p, []) for p in full_estate.processes]
    uplifts = [analyze_uplift(full_estate, s) for s in specs]
    doc = generate_report(full_estate, specs, uplifts, out_dir=tmp_path)
    md = doc.markdown_path.read_text(encoding="utf-8")
    for process in full_estate.processes:
        assert process.name in md
    # The feeder is low complexity but queue-coupled to the high-band
    # intake, so both land in wave 3.
    feeder_row = next(line for line in md.splitlines() if line.startswith("| MFG - Dispute Feeder"))
    assert feeder_row.rstrip().endswith("| 3 |")
    address_row = next(
        line for line in md.splitlines() if line.startswith("| MFG - Address Change")
    )
    assert address_row.rstrip().endswith("| 1 |")
    assert "queue-coupled" in md


def test_report_states_missing_specs_and_analysis_honestly(full_estate, tmp_path):
    doc = generate_report(full_estate, [], [], out_dir=tmp_path)
    md = doc.markdown_path.read_text(encoding="utf-8")
    assert "No intent spec" in md
