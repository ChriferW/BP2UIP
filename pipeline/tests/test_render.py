import json

from bp2uip.intent import extract_intent
from bp2uip.providers import FakeProvider
from bp2uip.render import spec_to_markdown
from conftest import good_extraction_response


def _spec(p03_estate, estate_ref):
    provider = FakeProvider([good_extraction_response(p03_estate)])
    return extract_intent(p03_estate, "MFG - Address Change", provider, estate_ref=estate_ref)


def test_markdown_resolves_citations_to_stage_names(p03_estate, estate_ref):
    spec = _spec(p03_estate, estate_ref)
    markdown = spec_to_markdown(spec, p03_estate)
    assert "# Intent spec: MFG - Address Change" in markdown
    # Cited stage ids are replaced by readable labels.
    cited = spec.purpose.citations[0]
    stage = next(s for p in p03_estate.processes for s in p.stages if s.id == cited)
    assert f"{stage.name} ({stage.type})" in markdown
    assert cited not in markdown
    assert "**draft**" in markdown


def test_markdown_without_estate_falls_back_to_raw_ids(p03_estate, estate_ref):
    spec = _spec(p03_estate, estate_ref)
    markdown = spec_to_markdown(spec, None)
    assert spec.purpose.citations[0] in markdown
    # Without the estate the process name is unknown; the id stands in.
    assert f"# Intent spec: {spec.process_id}" in markdown


def test_markdown_states_empty_sections_instead_of_omitting_them(p03_estate, estate_ref):
    spec = _spec(p03_estate, estate_ref)
    markdown = spec_to_markdown(spec, p03_estate)
    # The canned response has no touchpoints; the section says so.
    assert "## Human touchpoints" in markdown
    assert "None identified." in markdown


def test_markdown_shows_approval(p03_estate, estate_ref):
    spec = _spec(p03_estate, estate_ref)
    data = spec.model_dump()
    data["status"] = "approved"
    data["approval"] = {
        "approved_by": "Test Reviewer",
        "approved_at": "2026-07-20T00:00:00+00:00",
        "changes": [],
    }
    approved = spec.model_validate(data)
    markdown = spec_to_markdown(approved, p03_estate)
    assert "**approved**" in markdown
    assert "Approved by: **Test Reviewer**" in markdown


def test_markdown_survives_unknown_citation_id(p03_estate, estate_ref):
    spec = _spec(p03_estate, estate_ref)
    data = spec.model_dump()
    data["purpose"]["citations"] = ["not-a-real-stage"]
    broken = spec.model_validate(data)
    markdown = spec_to_markdown(broken, p03_estate)
    # Rendering never hides what a spec cites, even if it is wrong.
    assert "not-a-real-stage" in markdown


def test_extraction_response_helper_is_valid_json(p03_estate):
    json.loads(good_extraction_response(p03_estate))
