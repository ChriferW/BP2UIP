"""The review gate: the single choke point through which all generation passes.

PDD generation, SDD generation, and every emitter call require_approved
before doing anything else (ADR-004 in docs/master-plan.md). There is
no other path to generation.
"""

from bp2uip.model import IntentSpec
from bp2uip.provenance import ProvenanceLog


class UnapprovedSpecError(Exception):
    """Generation was attempted from a spec that has not passed review."""


def _has_approval_event(spec: IntentSpec, log: ProvenanceLog) -> bool:
    return any(
        e.event == "spec_approved" and e.detail.get("spec_id") == spec.spec_id for e in log.events()
    )


def require_approved(
    spec: IntentSpec, log: ProvenanceLog, *, force: bool = False, actor: str = "bp2uip"
) -> None:
    """Raise UnapprovedSpecError unless the spec is approved.

    Approval means both: the spec document carries status "approved"
    with an approval record, and the provenance log contains a matching
    spec_approved event. The two must agree.

    With force=True an unapproved spec is allowed through, but only
    after an unreviewed_generation event is appended to provenance. A
    forced run that cannot write provenance does not run.
    """
    if spec.status == "approved" and spec.approval is not None and _has_approval_event(spec, log):
        return
    if not force:
        raise UnapprovedSpecError(
            f"spec {spec.spec_id} is not approved (status: {spec.status}); "
            "generation refuses to run. Use --force only for demos: it is "
            "recorded in provenance as an unreviewed generation."
        )
    log.append(
        actor=actor,
        event="unreviewed_generation",
        detail={"spec_id": spec.spec_id, "spec_status": spec.status},
    )
