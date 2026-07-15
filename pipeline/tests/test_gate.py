import pytest

from bp2uip import docsgen, emitters
from bp2uip.gate import UnapprovedSpecError, require_approved
from bp2uip.intent import approve_spec
from bp2uip.model import UpliftReport, UpliftSpecRef, utc_now


def test_gate_refuses_draft_spec(draft_spec, log):
    with pytest.raises(UnapprovedSpecError):
        require_approved(draft_spec, log)


def test_gate_passes_spec_approved_through_the_lifecycle(draft_spec, log):
    approved = approve_spec(draft_spec, approved_by="Test Reviewer", log=log)
    require_approved(approved, log)  # must not raise


def test_gate_refuses_approved_status_without_provenance_event(draft_spec, log):
    # A spec document claiming approval that provenance does not confirm
    # is not approved. The two must agree.
    data = draft_spec.model_dump()
    data["status"] = "approved"
    data["approval"] = {
        "approved_by": "Someone",
        "approved_at": utc_now(),
        "changes": [],
    }
    from bp2uip.model import IntentSpec

    forged = IntentSpec.model_validate(data)
    with pytest.raises(UnapprovedSpecError):
        require_approved(forged, log)


def test_force_appends_exactly_one_unreviewed_generation_event(draft_spec, log):
    require_approved(draft_spec, log, force=True)  # must not raise
    events = log.events()
    assert len(events) == 1
    assert events[0].event == "unreviewed_generation"
    assert events[0].detail["spec_id"] == draft_spec.spec_id


def test_force_on_approved_spec_writes_no_event(draft_spec, log):
    approved = approve_spec(draft_spec, approved_by="Test Reviewer", log=log)
    before = len(log.events())
    require_approved(approved, log, force=True)
    assert len(log.events()) == before


def _uplift_report(spec):
    return UpliftReport(
        process_id=spec.process_id,
        spec_ref=UpliftSpecRef(spec_id=spec.spec_id, status_at_analysis=spec.status),
        analyzed_at=utc_now(),
        findings=[],
    )


def test_docsgen_refuses_draft_even_when_called_directly(draft_spec, log):
    with pytest.raises(UnapprovedSpecError):
        docsgen.generate_pdd(None, draft_spec, log)
    with pytest.raises(UnapprovedSpecError):
        docsgen.generate_sdd(None, draft_spec, _uplift_report(draft_spec), log)


def test_emitters_refuse_draft_even_when_called_directly(draft_spec, log):
    with pytest.raises(UnapprovedSpecError):
        emitters.emit_reframework(draft_spec, _uplift_report(draft_spec), log)
    with pytest.raises(UnapprovedSpecError):
        emitters.emit_bpmn(draft_spec, log)


def test_generators_pass_the_gate_on_approved_spec(draft_spec, log):
    # With an approved spec the gate passes and only the unimplemented
    # generation remains, proving the refusal above comes from the gate.
    approved = approve_spec(draft_spec, approved_by="Test Reviewer", log=log)
    with pytest.raises(NotImplementedError):
        docsgen.generate_pdd(None, approved, log)
    with pytest.raises(NotImplementedError):
        emitters.emit_bpmn(approved, log)
