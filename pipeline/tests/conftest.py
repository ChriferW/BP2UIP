import pytest

from bp2uip.model import (
    BusinessRule,
    EstateRef,
    Extraction,
    IntentSpec,
    PurposeSection,
    utc_now,
)
from bp2uip.provenance import ProvenanceLog


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
