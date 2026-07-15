import pytest

from bp2uip.intent import approve_spec
from bp2uip.model import SpecChange


def test_approve_spec_produces_approved_spec_and_provenance_event(draft_spec, log):
    approved = approve_spec(draft_spec, approved_by="Test Reviewer", log=log)
    assert approved.status == "approved"
    assert approved.approval is not None
    assert approved.approval.approved_by == "Test Reviewer"
    events = log.events()
    assert len(events) == 1
    assert events[0].event == "spec_approved"
    assert events[0].actor == "Test Reviewer"
    assert events[0].detail["spec_id"] == draft_spec.spec_id


def test_approve_spec_records_change_count(draft_spec, log):
    changes = [SpecChange(section="business_rules", before="a", after="b", note="fix")]
    approved = approve_spec(draft_spec, approved_by="Test Reviewer", log=log, changes=changes)
    assert approved.approval.changes == changes
    assert log.events()[0].detail["changes"] == 1


def test_approve_spec_requires_reviewer_identity(draft_spec, log):
    with pytest.raises(ValueError, match="never inferred"):
        approve_spec(draft_spec, approved_by="", log=log)
    with pytest.raises(ValueError, match="never inferred"):
        approve_spec(draft_spec, approved_by="   ", log=log)


def test_approve_spec_rejects_already_approved(draft_spec, log):
    approved = approve_spec(draft_spec, approved_by="Test Reviewer", log=log)
    with pytest.raises(ValueError, match="already approved"):
        approve_spec(approved, approved_by="Test Reviewer", log=log)


def test_original_draft_is_not_mutated(draft_spec, log):
    approve_spec(draft_spec, approved_by="Test Reviewer", log=log)
    assert draft_spec.status == "draft"
    assert draft_spec.approval is None
