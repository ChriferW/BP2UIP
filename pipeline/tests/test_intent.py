import json

import pytest

from bp2uip.intent import (
    PROMPT_VERSION,
    ExtractionError,
    approve_spec,
    build_extraction_prompt,
    extract_intent,
    find_process,
    validate_spec,
)
from bp2uip.model import SpecChange
from bp2uip.providers import FakeProvider
from conftest import good_extraction_response

# --------------------------------------------------------------------------
# extract_intent
# --------------------------------------------------------------------------


def test_extract_produces_valid_draft_spec(p03_estate, estate_ref):
    provider = FakeProvider([good_extraction_response(p03_estate)])
    spec = extract_intent(p03_estate, "MFG - Address Change", provider, estate_ref=estate_ref)
    assert spec.status == "draft"
    assert spec.approval is None
    assert spec.process_id == p03_estate.processes[0].id
    assert spec.spec_id == f"spec-{spec.process_id}"
    assert spec.extraction.provider == "fake"
    assert spec.extraction.model == "fake-model"
    assert spec.extraction.prompt_version == PROMPT_VERSION
    assert spec.estate_ref == estate_ref
    assert validate_spec(spec, p03_estate) == []


def test_extract_resolves_process_by_id(p03_estate, estate_ref):
    provider = FakeProvider([good_extraction_response(p03_estate)])
    process_id = p03_estate.processes[0].id
    spec = extract_intent(p03_estate, process_id, provider, estate_ref=estate_ref)
    assert spec.process_id == process_id


def test_extract_accepts_fenced_json(p03_estate, estate_ref):
    fenced = f"```json\n{good_extraction_response(p03_estate)}\n```"
    provider = FakeProvider([fenced])
    spec = extract_intent(p03_estate, "MFG - Address Change", provider, estate_ref=estate_ref)
    assert spec.status == "draft"


def test_extract_retries_once_on_malformed_output(p03_estate, estate_ref):
    provider = FakeProvider(["this is not JSON", good_extraction_response(p03_estate)])
    spec = extract_intent(p03_estate, "MFG - Address Change", provider, estate_ref=estate_ref)
    assert spec.status == "draft"
    assert len(provider.prompts) == 2
    assert "not valid JSON" in provider.prompts[1]


def test_extract_retries_on_hallucinated_citation(p03_estate, estate_ref):
    bad = json.loads(good_extraction_response(p03_estate))
    bad["business_rules"][0]["citations"] = ["stage-that-does-not-exist"]
    provider = FakeProvider([json.dumps(bad), good_extraction_response(p03_estate)])
    spec = extract_intent(p03_estate, "MFG - Address Change", provider, estate_ref=estate_ref)
    assert spec.status == "draft"
    assert "stage-that-does-not-exist" in provider.prompts[1]


def test_extract_fails_after_second_bad_response(p03_estate, estate_ref):
    provider = FakeProvider(["not JSON", "still not JSON"])
    with pytest.raises(ExtractionError, match="after one retry"):
        extract_intent(p03_estate, "MFG - Address Change", provider, estate_ref=estate_ref)


def test_extract_rejects_unknown_process(p03_estate, estate_ref):
    provider = FakeProvider([])
    with pytest.raises(ExtractionError, match="no process"):
        extract_intent(p03_estate, "No Such Process", provider, estate_ref=estate_ref)
    assert provider.prompts == []


def test_prompt_contains_process_and_referenced_object(p03_estate):
    process = find_process(p03_estate, "MFG - Address Change")
    prompt = build_extraction_prompt(p03_estate, process)
    assert process.id in prompt
    # P03 calls the Core Banking object; the extractor must see it.
    assert "MFG Core Banking" in prompt


# --------------------------------------------------------------------------
# validate_spec
# --------------------------------------------------------------------------


def test_validate_flags_unknown_and_missing_citations(draft_spec, p03_estate):
    # draft_spec cites stage-001/stage-002, which do not exist in P03.
    errors = validate_spec(draft_spec, p03_estate)
    locations = {e.location for e in errors}
    assert "purpose.citations[0]" in locations
    assert "business_rules[0].citations[0]" in locations


def test_validate_flags_empty_citations(draft_spec, p03_estate):
    data = draft_spec.model_dump()
    data["purpose"]["citations"] = []
    data["business_rules"] = []
    spec = draft_spec.model_validate(data)
    errors = validate_spec(spec, p03_estate)
    assert len(errors) == 1
    assert errors[0].location == "purpose"
    assert "at least one stage" in errors[0].message


# --------------------------------------------------------------------------
# approve_spec
# --------------------------------------------------------------------------


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
