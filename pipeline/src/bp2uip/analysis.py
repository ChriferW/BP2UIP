"""Analysis layer: complexity scoring, dependency graphing, uplift classification.

Implemented in roadmap week 4. The uplift analyzer implements
docs/uplift-criteria.md; the document is authoritative, findings cite
its rule IDs, and a contract test asserts every emitted ID exists in
the document. The default classification is deterministic, and every
other answer carries reasoning written against the specific stages.

Everything in this module is pure code over the estate model and the
intent spec. No LLM is involved in analysis.
"""

import re
from collections import defaultdict

from bp2uip.model import (
    ComplexityScore,
    DependencyGraph,
    Estate,
    EstateAnalysis,
    EstateRef,
    IntentSpec,
    ObjectFanIn,
    ObjectUse,
    Process,
    ProcessDependencies,
    QueueCoupling,
    QueueUse,
    Stage,
    UpliftFinding,
    UpliftReport,
    UpliftSpecRef,
    utc_now,
)

CRITERIA_VERSION = "0.1.0"  # must match the version line of docs/uplift-criteria.md

# Stages that carry no behavior: excluded from logic counts and from
# uplift coverage (docs/uplift-criteria.md, "Default and precedence").
STRUCTURAL_TYPES = {"start", "end", "note"}

# Scoring weights and bands for the composite complexity score. The
# score is an ordinal ranking heuristic; the weights say only that
# branching, loops, and exception geometry cost more migration effort
# than straight-line stages.
_WEIGHTS = {
    "logic_stage": 1,
    "decision": 2,
    "loop": 2,
    "object_call": 1,
    "queue_operation": 1,
    "exception_construct": 3,
}
_BAND_MEDIUM = 15
_BAND_HIGH = 40

# The Blue Prism internal work-queues VBO: its invocations are queue
# operations, not business-object dependencies.
_INTERNAL_OBJECT_PREFIX = "Blueprism.Automate"


def _successors(process: Process) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for link in process.links:
        out[link.from_stage].append(link.to_stage)
    return dict(out)


# --------------------------------------------------------------------------
# Complexity
# --------------------------------------------------------------------------


def _branching_depth(process: Process) -> int:
    """Maximum number of decision stages on any acyclic path from a
    start stage, following the process links."""
    stages = {s.id: s for s in process.stages}
    succ = _successors(process)
    seeds = [s.id for s in process.stages if s.type == "start"]
    if not seeds:
        targets = {link.to_stage for link in process.links}
        seeds = [s.id for s in process.stages if s.id not in targets] or list(stages)

    best = 0
    # Iterative DFS with an explicit per-path visited set; the graphs
    # are small, and loops in the source make cycles unavoidable.
    stack: list[tuple[str, frozenset[str], int]] = [(s, frozenset(), 0) for s in seeds]
    while stack:
        stage_id, on_path, depth = stack.pop()
        if stage_id in on_path or stage_id not in stages:
            continue
        if stages[stage_id].type == "decision":
            depth += 1
            best = max(best, depth)
        on_path = on_path | {stage_id}
        for nxt in succ.get(stage_id, []):
            stack.append((nxt, on_path, depth))
    return best


def _is_queue_operation(stage: Stage) -> bool:
    return stage.type in ("queue_read", "queue_write")


def score_complexity(estate: Estate) -> list[ComplexityScore]:
    scores = []
    for process in estate.processes:
        logic = [s for s in process.stages if s.type not in STRUCTURAL_TYPES]
        decisions = sum(1 for s in logic if s.type == "decision")
        loops = sum(1 for s in logic if s.type == "loop_start")
        object_calls = [
            s
            for s in logic
            if s.type in ("action", "subprocess_call")
            and not str(s.properties.get("object", "")).startswith(_INTERNAL_OBJECT_PREFIX)
        ]
        distinct_objects = sorted(
            {str(s.properties["object"]) for s in object_calls if s.properties.get("object")}
        )
        queue_ops = sum(1 for s in logic if _is_queue_operation(s))
        exception_constructs = sum(
            1 for s in logic if s.type in ("exception", "block", "recover", "resume")
        ) + len(process.exception_blocks)

        score = (
            _WEIGHTS["logic_stage"] * len(logic)
            + _WEIGHTS["decision"] * decisions
            + _WEIGHTS["loop"] * loops
            + _WEIGHTS["object_call"] * len(object_calls)
            + _WEIGHTS["queue_operation"] * queue_ops
            + _WEIGHTS["exception_construct"] * exception_constructs
        )
        band = "low" if score < _BAND_MEDIUM else "medium" if score < _BAND_HIGH else "high"
        scores.append(
            ComplexityScore(
                process_id=process.id,
                process_name=process.name,
                stage_count=len(process.stages),
                logic_stage_count=len(logic),
                decision_count=decisions,
                branching_depth=_branching_depth(process),
                loop_count=loops,
                object_call_count=len(object_calls),
                distinct_objects=distinct_objects,
                queue_operation_count=queue_ops,
                exception_construct_count=exception_constructs,
                exception_density=round(exception_constructs / len(logic), 3) if logic else 0.0,
                score=score,
                band=band,
            )
        )
    return scores


# --------------------------------------------------------------------------
# Dependency graph
# --------------------------------------------------------------------------


def _queue_operation_kind(stage: Stage) -> str:
    if stage.type == "queue_read":
        return "read"
    action = str(stage.properties.get("action", ""))
    if "add" in action.lower():
        return "add"
    return "disposition"


def build_dependency_graph(estate: Estate) -> DependencyGraph:
    process_deps = []
    fan_in: dict[str, list[str]] = defaultdict(list)
    producers: dict[str, list[str]] = defaultdict(list)
    consumers: dict[str, list[str]] = defaultdict(list)

    for process in estate.processes:
        object_actions: dict[str, set[str]] = defaultdict(set)
        queue_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"read": 0, "add": 0, "disposition": 0}
        )
        subprocesses: set[str] = set()

        for stage in process.stages:
            obj = str(stage.properties.get("object", ""))
            if stage.type == "action" and obj and not obj.startswith(_INTERNAL_OBJECT_PREFIX):
                object_actions[obj].add(str(stage.properties.get("action", "")))
            elif stage.type == "subprocess_call":
                subprocesses.add(str(stage.properties.get("process", stage.name)))

        # First pass: queue operations with an explicit queue name.
        named_ops = [
            (stage, str(stage.properties["queue_name"]))
            for stage in process.stages
            if _is_queue_operation(stage) and stage.properties.get("queue_name")
        ]
        for stage, queue in named_ops:
            queue_counts[queue][_queue_operation_kind(stage)] += 1
        # Second pass: dispositions and reads that name no queue act on
        # the current item; attribute them to the process's read queue
        # when it reads exactly one. Anything else stays unattributed
        # rather than guessed.
        read_queues = {q for (s, q) in named_ops if s.type == "queue_read"}
        for stage in process.stages:
            if _is_queue_operation(stage) and not stage.properties.get("queue_name"):
                if len(read_queues) == 1:
                    queue_counts[next(iter(read_queues))][_queue_operation_kind(stage)] += 1

        for queue, counts in queue_counts.items():
            if counts["read"]:
                consumers[queue].append(process.id)
            if counts["add"]:
                producers[queue].append(process.id)
        for obj in object_actions:
            fan_in[obj].append(process.id)

        process_deps.append(
            ProcessDependencies(
                process_id=process.id,
                process_name=process.name,
                objects=[
                    ObjectUse(object=obj, actions=sorted(actions))
                    for obj, actions in sorted(object_actions.items())
                ],
                queues=[
                    QueueUse(queue=q, reads=c["read"], adds=c["add"], dispositions=c["disposition"])
                    for q, c in sorted(queue_counts.items())
                ],
                subprocesses=sorted(subprocesses),
            )
        )

    all_queues = sorted(set(producers) | set(consumers))
    return DependencyGraph(
        processes=process_deps,
        object_fan_in=[ObjectFanIn(object=obj, used_by=ids) for obj, ids in sorted(fan_in.items())],
        queue_couplings=[
            QueueCoupling(queue=q, producers=producers.get(q, []), consumers=consumers.get(q, []))
            for q in all_queues
        ],
    )


def analyze_estate(estate: Estate, *, estate_ref: EstateRef) -> EstateAnalysis:
    return EstateAnalysis(
        analyzed_at=utc_now(),
        estate_ref=estate_ref,
        complexity=score_complexity(estate),
        dependencies=build_dependency_graph(estate),
    )


# --------------------------------------------------------------------------
# Uplift analyzer (implements docs/uplift-criteria.md)
# --------------------------------------------------------------------------

# AC-1: an equality comparison involving a collection field reference,
# in either direction. `<>` never matches: the character before `=` is
# a space or a bracket, never `<` or `>`.
_DOTTED_EQ = re.compile(r"\[[^\]]+\.[^\]]+\]\s*=[^=]|[^<>=]=\s*\[[^\]]+\.[^\]]+\]")
_DOTTED_REF = re.compile(r"\[([^\].]+)\.([^\]]+)\]")


def config_constants(process: Process) -> set[str]:
    """Data items with a non-empty scalar initial value that no stage
    writes (docs/uplift-criteria.md AC-3)."""
    written: set[str] = set()

    def note_store(target: object) -> None:
        if isinstance(target, str) and target:
            written.add(target.split(".")[0])

    for stage in process.stages:
        props = stage.properties
        note_store(props.get("store_in"))
        for step in props.get("steps", []) or []:
            if isinstance(step, dict):
                note_store(step.get("store_in"))
        for io_key in ("outputs", "inputs"):
            for entry in props.get(io_key, []) or []:
                if isinstance(entry, dict):
                    note_store(entry.get("store_in"))

    return {
        item.name
        for item in process.data_items
        if isinstance(item.initial_value, str | int | float)
        and str(item.initial_value) != ""
        and item.name not in written
    }


def _is_business_exception(stage: Stage) -> bool:
    return (
        stage.type == "exception"
        and "business" in str(stage.properties.get("exception_type", "")).lower()
    )


def _is_exception_disposition(stage: Stage) -> bool:
    return (
        stage.type == "queue_write"
        and "exception" in str(stage.properties.get("action", "")).lower()
    )


def _names(stages: list[Stage]) -> str:
    return ", ".join(f"'{s.name}'" for s in stages)


def analyze_uplift(estate: Estate, spec: IntentSpec) -> UpliftReport:
    """Classify every behavioral stage of the spec's process. Every
    stage outside STRUCTURAL_TYPES lands in exactly one finding; the
    coverage invariant is tested, not assumed."""
    process = next((p for p in estate.processes if p.id == spec.process_id), None)
    if process is None:
        raise ValueError(
            f"spec {spec.spec_id} references process {spec.process_id}, which is not in the estate"
        )

    stages = {s.id: s for s in process.stages}
    succ = _successors(process)
    claimed: set[str] = set()
    findings: list[UpliftFinding] = []

    def add(stage_ids: list[str], classification: str, reasoning: str, criteria: list[str]) -> None:
        findings.append(
            UpliftFinding(
                id=f"uf-{len(findings) + 1:02d}",
                stage_ids=stage_ids,
                classification=classification,  # type: ignore[arg-type]
                reasoning=reasoning,
                criteria=criteria,
            )
        )
        claimed.update(stage_ids)

    def unclaimed(predicate) -> list[Stage]:
        return [
            s
            for s in process.stages
            if s.id not in claimed and s.type not in STRUCTURAL_TYPES and predicate(s)
        ]

    # HG-1: one finding per spec-identified human touchpoint, claiming
    # the cited handoff stages (action, queue_write, exception). The
    # reviewed spec is authoritative on where humans sit.
    for touchpoint in spec.human_touchpoints:
        cited = [
            stages[cid]
            for cid in touchpoint.citations
            if cid in stages
            and cid not in claimed
            and stages[cid].type in ("action", "queue_write", "exception")
        ]
        if cited:
            add(
                [s.id for s in cited],
                "HUMAN_GATE",
                f"The reviewed intent spec identifies a human touchpoint here: "
                f'"{touchpoint.description}" The handoff stages ({_names(cited)}) '
                f"are the boundary; migration preserves it.",
                ["HG-1"],
            )

    # HG-2: exception dispositions the spec did not name.
    hg2 = unclaimed(lambda s: _is_exception_disposition(s) or _is_business_exception(s))
    if hg2:
        add(
            [s.id for s in hg2],
            "HUMAN_GATE",
            f"{_names(hg2)}: each ends automated handling and leaves the item "
            f"in a state a person must investigate and resolve.",
            ["HG-2"],
        )

    # AC-1: exact-match reconciliation decisions.
    def _is_reconciliation(s: Stage) -> bool:
        return s.type == "decision" and bool(
            _DOTTED_EQ.search(str(s.properties.get("expression", "")))
        )

    for stage in unclaimed(_is_reconciliation):
        expression = str(stage.properties.get("expression", ""))
        fields = sorted({f"{m.group(1)}.{m.group(2)}" for m in _DOTTED_REF.finditer(expression)})
        add(
            [stage.id],
            "AGENTIC_CANDIDATE",
            f"Decision '{stage.name}' matches records by exact equality "
            f"({expression}), comparing {', '.join(fields)}. Exact matching is "
            f"brittle against real-world variance; every near miss becomes a "
            f"human exception. Candidate: agentic matching proposes, "
            f"deterministic rules dispose, non-exact matches escalate with "
            f"reasoning attached.",
            ["AC-1"],
        )

    # AC-3: threshold-only triage into a human gate.
    config = config_constants(process)
    hg_stages = {sid for f in findings if f.classification == "HUMAN_GATE" for sid in f.stage_ids}
    for stage in unclaimed(lambda s: s.type == "decision"):
        expression = str(stage.properties.get("expression", ""))
        used_config = sorted(name for name in config if f"[{name}]" in expression)
        gated = [sid for sid in succ.get(stage.id, []) if sid in hg_stages]
        if used_config and gated:
            add(
                [stage.id],
                "AGENTIC_CANDIDATE",
                f"Decision '{stage.name}' routes work to a human gate "
                f"({_names([stages[sid] for sid in gated])}) on a single "
                f"configured threshold ({expression}; "
                f"{', '.join(used_config)} is configuration no stage writes). "
                f"The threshold is a deterministic proxy for a risk judgment. "
                f"Candidate: agent-assisted triage that may narrow, never "
                f"widen, what is auto-processed; the gate itself stays "
                f"(P-2 keeps the gate stages HUMAN_GATE).",
                ["AC-3", "P-2"],
            )

    # KD rules, lowest number first, one grouped finding per rule.
    kd_rules = [
        (
            "KD-1",
            lambda s: s.type == "calculation",
            "deterministic arithmetic and data staging; regulated amounts "
            "must not be model-mediated",
        ),
        (
            "KD-2",
            lambda s: s.type in ("action", "subprocess_call"),
            "invocations of defined interfaces; the target system's contract "
            "does not loosen because a model is upstream",
        ),
        (
            "KD-3",
            _is_queue_operation,
            "queue mechanics mapping directly to UiPath Orchestrator queue operations",
        ),
        (
            "KD-4",
            lambda s: s.type in ("decision", "loop_start", "loop_end"),
            "explicit flow control; the condition is fully stated in the "
            "source, there is no judgment to uplift",
        ),
        (
            "KD-5",
            lambda s: s.type in ("block", "recover", "resume", "exception"),
            "exception and retry geometry that becomes REFramework retry "
            "configuration and must remain exact",
        ),
    ]
    for rule_id, predicate, rationale in kd_rules:
        matched = unclaimed(predicate)
        if matched:
            add(
                [s.id for s in matched],
                "KEEP_DETERMINISTIC",
                f"{_names(matched)}: {rationale}.",
                [rule_id],
            )

    # P-1: the default for anything no rule claimed.
    rest = unclaimed(lambda s: True)
    if rest:
        add(
            [s.id for s in rest],
            "KEEP_DETERMINISTIC",
            f"{_names(rest)}: no rule matched; the default classification is deterministic.",
            ["P-1"],
        )

    return UpliftReport(
        process_id=process.id,
        spec_ref=UpliftSpecRef(spec_id=spec.spec_id, status_at_analysis=spec.status),
        analyzed_at=utc_now(),
        criteria_version=CRITERIA_VERSION,
        findings=findings,
    )
