"""Document generation: PDD, SDD, and the modernization report.

Implemented in roadmap week 5. Markdown is the primary output; DOCX is
produced via pandoc with a committed reference template. Every
generator passes through the review gate before doing anything else;
the gate call is the first line, not a decoration.
"""

from dataclasses import dataclass
from pathlib import Path

from bp2uip.gate import require_approved
from bp2uip.model import Estate, IntentSpec, UpliftReport
from bp2uip.provenance import ProvenanceLog


@dataclass
class GeneratedDoc:
    markdown_path: Path
    docx_path: Path | None = None


def generate_pdd(
    estate: Estate, spec: IntentSpec, log: ProvenanceLog, *, force: bool = False
) -> GeneratedDoc:
    """As-is process document from parser output plus approved intent."""
    require_approved(spec, log, force=force)
    raise NotImplementedError("PDD generation is roadmap week 5")


def generate_sdd(
    estate: Estate,
    spec: IntentSpec,
    uplift: UpliftReport,
    log: ProvenanceLog,
    *,
    force: bool = False,
) -> GeneratedDoc:
    """To-be design document from approved intent plus the emitter plan."""
    require_approved(spec, log, force=force)
    raise NotImplementedError("SDD generation is roadmap week 5")


def generate_report(
    estate: Estate, specs: list[IntentSpec], uplift_reports: list[UpliftReport]
) -> GeneratedDoc:
    """Per-process modernization summary: complexity, uplift findings, recommendation."""
    raise NotImplementedError("modernization report is roadmap week 5")
