"""Contract tests: the JSON Schema files, their examples, and the
Pydantic models must all agree, so the pipeline/dashboard contract
cannot drift silently."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from pydantic import ValidationError as PydanticValidationError

from bp2uip.model import (
    Estate,
    EstateAnalysis,
    IntentSpec,
    Manifest,
    ProvenanceEvent,
    UpliftReport,
    to_document,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schema"
EXAMPLES_DIR = SCHEMA_DIR / "examples"

ARTIFACT_TYPES = [
    ("estate", Estate),
    ("intent-spec", IntentSpec),
    ("provenance-event", ProvenanceEvent),
    ("uplift-finding", UpliftReport),
    ("estate-analysis", EstateAnalysis),
    ("manifest", Manifest),
]


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def load_example(name: str) -> dict:
    return json.loads((EXAMPLES_DIR / f"{name}.example.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", [n for n, _ in ARTIFACT_TYPES])
def test_schema_is_valid_json_schema(name):
    Draft202012Validator.check_schema(load_schema(name))


@pytest.mark.parametrize("name", [n for n, _ in ARTIFACT_TYPES])
def test_example_validates_against_schema(name):
    Draft202012Validator(load_schema(name)).validate(load_example(name))


@pytest.mark.parametrize(("name", "model_cls"), ARTIFACT_TYPES)
def test_pydantic_model_round_trips_through_schema(name, model_cls):
    model = model_cls.model_validate(load_example(name))
    Draft202012Validator(load_schema(name)).validate(to_document(model))


def test_approved_spec_without_approval_fails_schema():
    doc = load_example("intent-spec")
    assert doc["status"] == "approved"
    doc["approval"] = None
    with pytest.raises(ValidationError):
        Draft202012Validator(load_schema("intent-spec")).validate(doc)


def test_approved_spec_without_approval_fails_pydantic():
    doc = load_example("intent-spec")
    doc["approval"] = None
    with pytest.raises(PydanticValidationError):
        IntentSpec.model_validate(doc)


def test_draft_spec_with_approval_fails_schema_and_pydantic():
    doc = load_example("intent-spec")
    doc["status"] = "draft"  # approval record still present
    with pytest.raises(ValidationError):
        Draft202012Validator(load_schema("intent-spec")).validate(doc)
    with pytest.raises(PydanticValidationError):
        IntentSpec.model_validate(doc)
