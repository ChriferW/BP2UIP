"""Analysis layer: complexity scoring, dependency graphing, uplift classification.

Implemented in roadmap week 4. The uplift analyzer implements
docs/uplift-criteria.md, which is written before the code; its default
answer is deterministic, and any other classification must carry
reasoning and criteria references.
"""

from dataclasses import dataclass

from bp2uip.model import Estate, IntentSpec, UpliftReport


@dataclass
class ComplexityScore:
    """Per-process migration-effort score. Dimensions defined in week 4:
    stage counts, branching depth, object fan-in, exception density."""

    process_id: str


@dataclass
class DependencyGraph:
    """Processes and shared objects with their references. Shape defined in week 4."""


def score_complexity(estate: Estate) -> list[ComplexityScore]:
    raise NotImplementedError("complexity scoring is roadmap week 4")


def build_dependency_graph(estate: Estate) -> DependencyGraph:
    raise NotImplementedError("dependency graphing is roadmap week 4")


def analyze_uplift(estate: Estate, spec: IntentSpec) -> UpliftReport:
    raise NotImplementedError("uplift analysis is roadmap week 4")
