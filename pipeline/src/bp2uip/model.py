"""Pydantic models for every artifact type.

These are the same shapes as the JSON Schema files in schema/; a
contract test asserts they agree. Field additions are non-breaking,
renames are breaking. See docs/master-plan.md section 2.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = "0.1.0"


def utc_now() -> str:
    """Current UTC time as ISO 8601, the timestamp format of every artifact."""
    return datetime.now(UTC).isoformat()


def to_document(model: BaseModel) -> dict[str, Any]:
    """Serialize a model to its JSON artifact shape.

    Manifests omit absent artifacts entirely (the manifest never claims
    an artifact that does not exist); every other artifact serializes
    all fields, including explicit nulls such as a draft spec's
    approval.
    """
    exclude_none = isinstance(model, Manifest)
    return model.model_dump(mode="json", exclude_none=exclude_none)


# --------------------------------------------------------------------------
# Estate model (schema/estate.schema.json)
# --------------------------------------------------------------------------

StageType = Literal[
    "decision",
    "calculation",
    "action",
    "loop_start",
    "loop_end",
    "exception",
    "block",
    "recover",
    "resume",
    "subprocess_call",
    "queue_read",
    "queue_write",
    "note",
    "data",
    "start",
    "end",
    "unknown",
]


class SourceFile(BaseModel):
    path: str
    sha256: str


class EstateSource(BaseModel):
    files: list[SourceFile]
    parsed_at: str
    parser_version: str


class Stage(BaseModel):
    id: str
    name: str
    type: StageType
    raw_type: str  # verbatim type string from the source XML, always preserved
    properties: dict[str, Any] = Field(default_factory=dict)


class DataItem(BaseModel):
    id: str
    name: str
    data_type: str
    initial_value: Any = None


class Link(BaseModel):
    from_stage: str
    to_stage: str
    label: str | None = None


class ExceptionBlock(BaseModel):
    id: str
    covers_stages: list[str]
    handler_stage: str


class Process(BaseModel):
    id: str
    name: str
    description: str = ""
    stages: list[Stage]
    data_items: list[DataItem]
    links: list[Link]
    exception_blocks: list[ExceptionBlock]


class ObjectAction(BaseModel):
    id: str
    name: str
    stages: list[Stage] = Field(default_factory=list)


class EstateObject(BaseModel):
    id: str
    name: str
    actions: list[ObjectAction]


class Queue(BaseModel):
    id: str
    name: str
    key_field: str | None = None
    max_attempts: int | None = None


class UnparsedElement(BaseModel):
    """An element the parser saw but did not understand. Honesty mechanism."""

    element: str
    location: str
    note: str


class Estate(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source: EstateSource
    processes: list[Process]
    objects: list[EstateObject]
    queues: list[Queue]
    unparsed: list[UnparsedElement] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Intent spec (schema/intent-spec.schema.json)
# --------------------------------------------------------------------------

SpecStatus = Literal["draft", "approved"]


class EstateRef(BaseModel):
    path: str
    sha256: str


class Extraction(BaseModel):
    provider: str
    model: str
    prompt_version: str


class PurposeSection(BaseModel):
    text: str
    citations: list[str]


class InputItem(BaseModel):
    name: str
    description: str
    source: str = ""
    citations: list[str]


class OutputItem(BaseModel):
    name: str
    description: str
    destination: str = ""
    citations: list[str]


class BusinessRule(BaseModel):
    id: str
    statement: str
    citations: list[str]


class ExceptionSemantic(BaseModel):
    condition: str
    current_handling: str
    citations: list[str]


class HumanTouchpoint(BaseModel):
    description: str
    citations: list[str]


class SpecChange(BaseModel):
    section: str
    before: str
    after: str
    note: str = ""


class Approval(BaseModel):
    approved_by: str = Field(min_length=1)
    approved_at: str
    changes: list[SpecChange] = Field(default_factory=list)


class IntentSpec(BaseModel):
    schema_version: str = SCHEMA_VERSION
    spec_id: str
    process_id: str
    estate_ref: EstateRef
    status: SpecStatus = "draft"
    created_at: str
    extraction: Extraction
    purpose: PurposeSection
    inputs: list[InputItem]
    outputs: list[OutputItem]
    business_rules: list[BusinessRule]
    exception_semantics: list[ExceptionSemantic]
    human_touchpoints: list[HumanTouchpoint]
    approval: Approval | None = None

    @model_validator(mode="after")
    def _lifecycle_invariant(self) -> "IntentSpec":
        if self.status == "approved" and self.approval is None:
            raise ValueError("an approved spec must carry an approval record")
        if self.status == "draft" and self.approval is not None:
            raise ValueError("a draft spec must not carry an approval record")
        return self


# --------------------------------------------------------------------------
# Provenance event (schema/provenance-event.schema.json)
# --------------------------------------------------------------------------

EventType = Literal[
    "parsed",
    "extraction_run",
    "spec_drafted",
    "spec_corrected",
    "spec_approved",
    "generation",
    "unreviewed_generation",
    "report_generated",
]


class ProvenanceEvent(BaseModel):
    schema_version: str = SCHEMA_VERSION
    process_id: str
    seq: int = Field(ge=1)
    prev_hash: str | None
    timestamp: str
    actor: str = Field(min_length=1)
    event: EventType
    detail: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Uplift report (schema/uplift-finding.schema.json)
# --------------------------------------------------------------------------

Classification = Literal["AGENTIC_CANDIDATE", "KEEP_DETERMINISTIC", "HUMAN_GATE"]


class UpliftSpecRef(BaseModel):
    spec_id: str
    status_at_analysis: SpecStatus


class UpliftFinding(BaseModel):
    id: str
    stage_ids: list[str] = Field(min_length=1)
    classification: Classification
    reasoning: str = Field(min_length=1)
    criteria: list[str]  # rule IDs in docs/uplift-criteria.md


class UpliftReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    process_id: str
    spec_ref: UpliftSpecRef
    analyzed_at: str
    findings: list[UpliftFinding]


# --------------------------------------------------------------------------
# Manifest (schema/manifest.schema.json)
# --------------------------------------------------------------------------

EmittedKind = Literal["xaml", "bpmn", "config", "queue_manifest"]


class FileRef(BaseModel):
    path: str
    sha256: str


class FileRefVersioned(FileRef):
    schema_version: str


class SpecArtifactRef(FileRefVersioned):
    status: SpecStatus


class ProvenanceRef(BaseModel):
    path: str
    events: int = Field(ge=0)


class EmittedRef(FileRef):
    kind: EmittedKind


class ManifestArtifacts(BaseModel):
    estate: FileRefVersioned | None = None
    intent_spec: SpecArtifactRef | None = None
    uplift: FileRefVersioned | None = None
    provenance: ProvenanceRef | None = None
    pdd: FileRef | None = None
    sdd: FileRef | None = None
    emitted: list[EmittedRef] | None = None
    report: FileRef | None = None


class Manifest(BaseModel):
    schema_version: str = SCHEMA_VERSION
    process_id: str
    process_name: str
    generated_at: str
    pipeline_version: str
    artifacts: ManifestArtifacts
