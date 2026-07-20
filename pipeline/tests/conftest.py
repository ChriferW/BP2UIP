import json
from pathlib import Path

import pytest

from bp2uip.model import (
    BusinessRule,
    Estate,
    EstateRef,
    Extraction,
    IntentSpec,
    PurposeSection,
    utc_now,
)
from bp2uip.parser import parse_release
from bp2uip.provenance import ProvenanceLog

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture(scope="session")
def p03_estate() -> Estate:
    return parse_release([FIXTURES / "meridian-p03-address-change.bprelease"])


@pytest.fixture
def estate_ref() -> EstateRef:
    return EstateRef(path="artifacts/estate/estate.json", sha256="0" * 64)


def good_extraction_response(estate: Estate) -> str:
    """A canned provider response citing real stage ids from the estate."""
    stage_ids = [s.id for s in estate.processes[0].stages]
    return json.dumps(
        {
            "purpose": {
                "text": "Updates a customer's registered address in core banking.",
                "citations": [stage_ids[0]],
            },
            "inputs": [
                {
                    "name": "Address change request",
                    "description": "The pending change request.",
                    "source": "Core banking work basket",
                    "citations": [stage_ids[1]],
                }
            ],
            "outputs": [],
            "business_rules": [
                {
                    "id": "BR-1",
                    "statement": "Only active accounts may have their address changed.",
                    "citations": [stage_ids[2]],
                }
            ],
            "exception_semantics": [],
            "human_touchpoints": [],
        }
    )


@pytest.fixture
def draft_spec() -> IntentSpec:
    return IntentSpec(
        spec_id="spec-test-001",
        process_id="proc-test",
        estate_ref=EstateRef(path="artifacts/estate/estate.json", sha256="0" * 64),
        status="draft",
        created_at=utc_now(),
        extraction=Extraction(provider="fake", model="fake-model", prompt_version="0.1.0"),
        purpose=PurposeSection(text="Test process.", citations=["stage-001"]),
        inputs=[],
        outputs=[],
        business_rules=[BusinessRule(id="BR-1", statement="Test rule.", citations=["stage-002"])],
        exception_semantics=[],
        human_touchpoints=[],
        approval=None,
    )


@pytest.fixture
def log(tmp_path) -> ProvenanceLog:
    return ProvenanceLog.open(tmp_path / "provenance.jsonl", "proc-test")
