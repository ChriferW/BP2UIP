"""IR: intent extraction and the spec lifecycle.

extract_intent turns one process (plus the objects and queues it
references) into a prompt, sends it through the provider interface, and
validates the response into a draft IntentSpec. validate_spec is the
anti-hallucination check: every citation must name a stage id that
actually exists in the estate. approve_spec is the only way a spec
becomes approved, and it records the transition in provenance.
"""

import json
from dataclasses import dataclass

from bp2uip.model import (
    Approval,
    Estate,
    EstateRef,
    Extraction,
    IntentSpec,
    Process,
    SpecChange,
    to_document,
    utc_now,
)
from bp2uip.provenance import ProvenanceLog
from bp2uip.providers import CompletionResult, LLMProvider

# Bumped whenever the prompt text changes; recorded in every spec's
# extraction metadata so a spec can be traced to the prompt that made it.
PROMPT_VERSION = "0.1.0"

SYSTEM_PROMPT = (
    "You are a business analyst documenting a Blue Prism RPA process for "
    "migration. You are given the parsed structure of one process: its "
    "stages, data items, links, exception blocks, and the objects and "
    "work queues it references. Your job is to state the business intent "
    "of the process, not to describe its mechanics stage by stage. Every "
    "claim you make must cite the id of at least one stage that supports "
    "it, using stage ids exactly as they appear in the input. Never "
    "invent a stage id. If something is not evidenced by a stage, do not "
    "claim it. Respond with a single JSON object and nothing else."
)

_RESPONSE_FORMAT = """Respond with a single JSON object with exactly these keys:

{
  "purpose": {"text": "<one paragraph: what this process achieves and why>",
              "citations": ["<stage id>", "..."]},
  "inputs": [{"name": "...", "description": "...", "source": "<where it comes from>",
              "citations": ["..."]}],
  "outputs": [{"name": "...", "description": "...", "destination": "<where it goes>",
               "citations": ["..."]}],
  "business_rules": [{"id": "BR-1", "statement": "<a rule the process enforces>",
                      "citations": ["..."]}],
  "exception_semantics": [{"condition": "<what goes wrong>",
                           "current_handling": "<what the process does about it>",
                           "citations": ["..."]}],
  "human_touchpoints": [{"description": "<where a person is or should be involved>",
                         "citations": ["..."]}]
}

Rules:
- Every entry's "citations" list must contain at least one stage id from the input.
- Cite stage ids verbatim; never invent or alter one.
- Business rules are numbered BR-1, BR-2, and so on.
- An empty list is correct when a section genuinely has no entries.
- Output raw JSON only: no markdown fences, no commentary."""


class ExtractionError(Exception):
    """Extraction failed: process not found, or the provider's output
    could not be validated even after one retry."""


@dataclass
class SpecError:
    location: str
    message: str


def find_process(estate: Estate, process_ref: str) -> Process:
    """Resolve a process by id or exact name."""
    for process in estate.processes:
        if process.id == process_ref or process.name == process_ref:
            return process
    names = ", ".join(p.name for p in estate.processes) or "none"
    raise ExtractionError(
        f"no process with id or name '{process_ref}' in the estate (processes: {names})"
    )


def _referenced_components(estate: Estate, process: Process):
    """The objects and queues this process actually touches, by name."""
    object_names: set[str] = set()
    queue_names: set[str] = set()
    for stage in process.stages:
        props = stage.properties
        if props.get("object"):
            object_names.add(props["object"])
        if props.get("queue_name"):
            queue_names.add(props["queue_name"])
    objects = [o for o in estate.objects if o.name in object_names]
    queues = [q for q in estate.queues if q.name in queue_names]
    return objects, queues


def build_extraction_prompt(estate: Estate, process: Process) -> str:
    """The versioned prompt (PROMPT_VERSION) for one process."""
    objects, queues = _referenced_components(estate, process)
    payload = {
        "process": to_document(process),
        "referenced_objects": [to_document(o) for o in objects],
        "referenced_queues": [to_document(q) for q in queues],
    }
    return (
        "Extract the business intent of the following Blue Prism process.\n\n"
        f"{_RESPONSE_FORMAT}\n\n"
        "Input (parsed from the .bprelease export):\n"
        f"{json.dumps(payload, indent=2)}"
    )


def _strip_fences(text: str) -> str:
    """Tolerate a response wrapped in markdown code fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        stripped = stripped[first_newline + 1 :] if first_newline != -1 else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


def _spec_from_response(
    result: CompletionResult,
    provider_name: str,
    process: Process,
    estate: Estate,
    estate_ref: EstateRef,
) -> tuple[IntentSpec | None, list[str]]:
    """Build and validate a draft spec from one provider response.

    Returns (spec, []) on success, or (None, problems) where problems
    are the messages fed back to the provider on the retry.
    """
    try:
        data = json.loads(_strip_fences(result.text))
    except json.JSONDecodeError as exc:
        return None, [f"response is not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, ["response must be a JSON object"]
    try:
        spec = IntentSpec(
            spec_id=f"spec-{process.id}",
            process_id=process.id,
            estate_ref=estate_ref,
            status="draft",
            created_at=utc_now(),
            extraction=Extraction(
                provider=provider_name, model=result.model, prompt_version=PROMPT_VERSION
            ),
            purpose=data.get("purpose"),
            inputs=data.get("inputs"),
            outputs=data.get("outputs"),
            business_rules=data.get("business_rules"),
            exception_semantics=data.get("exception_semantics"),
            human_touchpoints=data.get("human_touchpoints"),
            approval=None,
        )
    except ValueError as exc:
        return None, [f"response does not match the required shape: {exc}"]
    errors = validate_spec(spec, estate)
    if errors:
        return None, [f"{e.location}: {e.message}" for e in errors]
    return spec, []


def _retry_prompt(original_prompt: str, bad_response: str, problems: list[str]) -> str:
    listed = "\n".join(f"- {p}" for p in problems)
    return (
        f"{original_prompt}\n\n"
        "Your previous response was rejected for these reasons:\n"
        f"{listed}\n\n"
        "Previous response:\n"
        f"{bad_response}\n\n"
        "Produce a corrected response. Follow the format rules exactly and "
        "cite only stage ids that appear in the input."
    )


def extract_intent(
    estate: Estate, process_id: str, provider: LLMProvider, *, estate_ref: EstateRef
) -> IntentSpec:
    """Extract a draft intent spec for one process.

    One retry on invalid output: the provider gets its rejected response
    back with the validation problems and one chance to correct it.
    """
    process = find_process(estate, process_id)
    prompt = build_extraction_prompt(estate, process)
    result = provider.complete(prompt, system=SYSTEM_PROMPT)
    spec, problems = _spec_from_response(result, provider.name, process, estate, estate_ref)
    if spec is not None:
        return spec
    retry = provider.complete(_retry_prompt(prompt, result.text, problems), system=SYSTEM_PROMPT)
    spec, problems = _spec_from_response(retry, provider.name, process, estate, estate_ref)
    if spec is not None:
        return spec
    raise ExtractionError(
        "provider output failed validation after one retry: " + "; ".join(problems)
    )


def validate_spec(spec: IntentSpec, estate: Estate) -> list[SpecError]:
    """The citation rule, enforced.

    Every section entry must cite at least one stage id, and every
    cited id must exist in the estate (process stages or object action
    stages). This is what stops the extractor from asserting intent the
    source XML does not evidence.
    """
    known: set[str] = set()
    for process in estate.processes:
        known.update(stage.id for stage in process.stages)
    for obj in estate.objects:
        for action in obj.actions:
            known.update(stage.id for stage in action.stages)

    errors: list[SpecError] = []

    def check(location: str, citations: list[str]) -> None:
        if not citations:
            errors.append(
                SpecError(location, "no citations: every claim must cite at least one stage")
            )
        for i, cited in enumerate(citations):
            if cited not in known:
                errors.append(
                    SpecError(
                        f"{location}.citations[{i}]",
                        f"citation '{cited}' does not name a stage in the estate",
                    )
                )

    check("purpose", spec.purpose.citations)
    for i, item in enumerate(spec.inputs):
        check(f"inputs[{i}]", item.citations)
    for i, item in enumerate(spec.outputs):
        check(f"outputs[{i}]", item.citations)
    for i, rule in enumerate(spec.business_rules):
        check(f"business_rules[{i}]", rule.citations)
    for i, semantic in enumerate(spec.exception_semantics):
        check(f"exception_semantics[{i}]", semantic.citations)
    for i, touchpoint in enumerate(spec.human_touchpoints):
        check(f"human_touchpoints[{i}]", touchpoint.citations)
    return errors


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
