"""Back-end: UiPath artifacts generated from approved intent, not from syntax.

Jinja2-templated emission of REFramework .xaml scaffolding (roadmap
week 6) and Maestro BPMN (week 7). Emission covers the mapped stage
vocabulary only; wherever human judgment is required the output carries
an explicit TODO marker citing the intent-spec clause it comes from.
Every emitter passes through the review gate first.
"""

from dataclasses import dataclass
from pathlib import Path

from bp2uip.gate import require_approved
from bp2uip.model import IntentSpec, UpliftReport
from bp2uip.provenance import ProvenanceLog


@dataclass
class EmittedArtifact:
    kind: str
    path: Path


@dataclass
class EmittedProject:
    root: Path
    artifacts: list[EmittedArtifact]


def emit_reframework(
    spec: IntentSpec, uplift: UpliftReport, log: ProvenanceLog, *, force: bool = False
) -> EmittedProject:
    """REFramework skeleton with Config.xlsx and queue manifests."""
    require_approved(spec, log, force=force)
    raise NotImplementedError("REFramework emission is roadmap week 6")


def emit_bpmn(spec: IntentSpec, log: ProvenanceLog, *, force: bool = False) -> EmittedArtifact:
    """Maestro BPMN for orchestration-shaped processes."""
    require_approved(spec, log, force=force)
    raise NotImplementedError("Maestro BPMN emission is roadmap week 7")
