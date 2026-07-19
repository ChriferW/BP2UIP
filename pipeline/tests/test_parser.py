"""Parser tests, keyed to the fixture feature matrix in
docs/master-plan.md section 5. Each matrix feature is asserted against
the real week 1 fixture export that carries it; the whole-estate test
sweeps every fixture file."""

from pathlib import Path

import pytest

from bp2uip.parser import ParseError, parse_release

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
ALL_FIXTURES = sorted(FIXTURES.glob("*.bprelease"))


@pytest.fixture(scope="module")
def estate():
    return parse_release([FIXTURES / "meridian-estate.bprelease"])


def process_named(estate, name):
    return next(p for p in estate.processes if p.name == name)


def stage_named(process, name):
    return next(s for s in process.stages if s.name == name)


def test_fixture_files_exist():
    assert len(ALL_FIXTURES) == 5


def test_missing_file_raises_parse_error():
    with pytest.raises(ParseError):
        parse_release([Path("fixtures/does-not-exist.bprelease")])


def test_decision_stages_parsed_with_links_and_labels(estate):
    p03 = process_named(estate, "MFG - Address Change")
    decision = stage_named(p03, "Account Active?")
    assert decision.type == "decision"
    assert decision.raw_type == "Decision"
    assert decision.properties["expression"] == '[AccountStatus] = "Active"'
    labels = {link.label: link.to_stage for link in p03.links if link.from_stage == decision.id}
    assert set(labels) == {"true", "false"}
    assert labels["true"] == stage_named(p03, "MFG Core Banking::Update Account Status").id
    assert labels["false"] == stage_named(p03, "Throw Inactive Account").id


def test_calculation_expression_captured_in_properties(estate):
    p01 = process_named(estate, "MFG - Card Dispute Intake")
    calc = stage_named(p01, "Compute Fee Refund")
    assert calc.type == "calculation"
    assert calc.properties["expression"] == "[DisputeAmount] * [FeeRate]"
    assert calc.properties["store_in"] == "FeeRefund"
    multi = stage_named(p01, "Unpack Dispute Item")
    assert multi.type == "calculation"
    assert multi.raw_type == "MultipleCalculation"
    assert {
        "expression": "[ItemData.DisputeRef]",
        "store_in": "DisputeRef",
    } in multi.properties["steps"]


def test_loop_pairing_and_body_membership(estate):
    p06 = process_named(estate, "MFG - Dispute Feeder")
    starts = [s for s in p06.stages if s.type == "loop_start"]
    ends = [s for s in p06.stages if s.type == "loop_end"]
    assert len(starts) == len(ends) == 1
    start, end = starts[0], ends[0]
    assert start.properties["collection"] == "Disputes"
    assert start.properties["group_id"] == end.properties["group_id"]
    assert start.properties["pair_stage_id"] == end.id
    assert end.properties["pair_stage_id"] == start.id
    body_names = {
        stage.name for stage in p06.stages if stage.id in start.properties["body_stage_ids"]
    }
    # "Stage Dsipute Row" is a real typo in the authored fixture, kept
    # as-is: legacy estates contain typos and the parser must not care.
    assert {"Stage Dsipute Row", "Add Dispute To Queue", "Count Loaded"} <= body_names


def test_exception_block_covers_and_handler_resolved(estate):
    p01 = process_named(estate, "MFG - Card Dispute Intake")
    assert len(p01.exception_blocks) == 1
    block = p01.exception_blocks[0]
    assert block.id == stage_named(p01, "Posting Attempt").id
    assert block.handler_stage == stage_named(p01, "Posting Failed").id
    assert stage_named(p01, "Posting Failed").type == "recover"
    assert block.covers_stages == [stage_named(p01, "Post Adjustment").id]
    resume_types = {s.name: s.type for s in p01.stages if s.raw_type == "Resume"}
    assert resume_types == {"Retry Posting": "resume", "Give Up": "resume"}


def test_sub_object_call_cross_references_object_action(estate):
    p03 = process_named(estate, "MFG - Address Change")
    call = stage_named(p03, "Lookup Account")
    assert call.type == "action"
    assert call.properties["object"] == "MFG Core Banking"
    assert call.properties["action"] == "Lookup Account"
    target = next(o for o in estate.objects if o.name == call.properties["object"])
    assert call.properties["action"] in {a.name for a in target.actions}


def test_queue_stages_linked_to_a_named_queue(estate):
    p01 = process_named(estate, "MFG - Card Dispute Intake")
    read = stage_named(p01, "Get Next Dispute")
    assert read.type == "queue_read"
    assert read.properties["queue_name"] == "Q-Disputes"
    p06 = process_named(estate, "MFG - Dispute Feeder")
    write = stage_named(p06, "Add Dispute To Queue")
    assert write.type == "queue_write"
    assert write.properties["queue_name"] == "Q-Disputes"
    queue = next(q for q in estate.queues if q.name == "Q-Disputes")
    assert queue.key_field == "DisputeRef"
    assert queue.max_attempts == 3


@pytest.mark.parametrize("path", ALL_FIXTURES, ids=lambda p: p.stem)
def test_whole_estate_parses_with_zero_unparsed_entries(path):
    estate = parse_release([path])
    assert estate.unparsed == []
    assert estate.processes  # every fixture contains at least one process


def test_multi_file_parse_deduplicates_shared_components():
    estate = parse_release(ALL_FIXTURES)
    assert len(estate.processes) == 4
    assert len(estate.objects) == 2
    assert len(estate.queues) == 3
    assert len(estate.source.files) == 5
