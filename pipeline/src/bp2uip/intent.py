"""IR: intent extraction and the spec lifecycle.

Extraction (estate chunk to prompt to validated draft spec) is
implemented in roadmap week 3. The lifecycle transition to approved is
implemented here now because the review gate depends on it.
"""

from dataclasses import dataclass

from bp2uip.model import Approval, Estate, IntentSpec, SpecChange, utc_now
from bp2uip.provenance import ProvenanceLog
from bp2uip.providers import LLMProvider


@dataclass
class SpecError:
    location: str
    message: str


def extract_intent(estate: Estate, process_id: str, provider: LLMProvider) -> IntentSpec:
    """Extract a draft intent spec for one process. Roadmap week 3."""
    raise NotImplementedError("intent extraction is roadmap week 3")


def validate_spec(spec: IntentSpec, estate: Estate) -> list[SpecError]:
    """Check that every citation names a stage that exists in the estate. Roadmap week 3."""
    raise NotImplementedError("citation validation is roadmap week 3")


def approve_spec(
    spec: IntentSpec,
    *,
    approved_by: str,
    log: ProvenanceLog,
    changes: list[SpecChange] | None = None,
) -> IntentSpec:
    """Transition a draft spec to approved and record it in provenance.

    approved_by is required and never inferred from git config or the
    environment: a tool whose thesis is provenance does not guess who
    approved something.
    """
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by is required; approval identity is never inferred")
    if spec.status == "approved":
        raise ValueError(f"spec {spec.spec_id} is already approved")
    data = spec.model_dump()
    data["status"] = "approved"
    data["approval"] = Approval(
        approved_by=approved_by,
        approved_at=utc_now(),
        changes=changes or [],
    ).model_dump()
    approved = IntentSpec.model_validate(data)
    log.append(
        actor=approved_by,
        event="spec_approved",
        detail={"spec_id": spec.spec_id, "changes": len(changes or [])},
    )
    return approved
