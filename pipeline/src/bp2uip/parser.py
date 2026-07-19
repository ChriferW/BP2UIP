"""Front-end: .bprelease XML in, platform-neutral estate model out.

This is the only module that reads Blue Prism formats. The
implementation is built against the real fixture exports in fixtures/
(authored in Blue Prism v7.5.1, roadmap week 1); every structural
assumption below was read from those files, not from documentation.

Honesty contract (docs/master-plan.md sections 2.1 and 3): every stage
keeps its verbatim raw_type string, and any element the parser does
not understand is recorded in Estate.unparsed rather than silently
dropped. Canvas chrome that the parser understands and deliberately
does not model is listed in SKIPPED_STAGE_TYPES / SKIPPED_ELEMENTS and
documented in the week 2 build-log entry; those skips do not appear in
unparsed because they are decisions, not gaps.
"""

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from bp2uip.model import (
    DataItem,
    Estate,
    EstateObject,
    EstateSource,
    ExceptionBlock,
    Link,
    ObjectAction,
    Process,
    Queue,
    SourceFile,
    Stage,
    UnparsedElement,
    utc_now,
)

PARSER_VERSION = "0.1.0"

RELEASE_NS = "{http://www.blueprism.co.uk/product/release}"
PROCESS_NS = "{http://www.blueprism.co.uk/product/process}"
QUEUE_NS = "{http://www.blueprism.co.uk/product/work-queue}"

# Blue Prism's built-in Work Queues business object as it appears in
# exported <resource object="..."> attributes.
WORK_QUEUES_OBJECT = "Blueprism.Automate.clsWorkQueuesActions"
QUEUE_READ_ACTIONS = {"Get Next Item"}
QUEUE_WRITE_ACTIONS = {"Add To Queue", "Mark Completed", "Mark Exception", "Defer"}

# Canvas chrome: understood, deliberately not modeled.
# ProcessInfo/SubSheetInfo are the info boxes Blue Prism draws on every
# page; the release-level groups only mirror the Studio tree folders.
SKIPPED_STAGE_TYPES = {"ProcessInfo", "SubSheetInfo"}
SKIPPED_ELEMENTS = {
    f"{RELEASE_NS}name",
    f"{RELEASE_NS}release-notes",
    f"{RELEASE_NS}created",
    f"{RELEASE_NS}package-id",
    f"{RELEASE_NS}package-name",
    f"{RELEASE_NS}user-created-by",
    f"{RELEASE_NS}process-group",
    f"{RELEASE_NS}object-group",
    f"{PROCESS_NS}view",
    f"{PROCESS_NS}preconditions",
    f"{PROCESS_NS}endpoint",
    f"{PROCESS_NS}appdef",
    f"{PROCESS_NS}subsheet",
    f"{PROCESS_NS}stage",
}

STAGE_TYPE_MAP = {
    "Start": "start",
    "End": "end",
    "Decision": "decision",
    "Calculation": "calculation",
    "MultipleCalculation": "calculation",
    "Note": "note",
    "Exception": "exception",
    "Block": "block",
    "Recover": "recover",
    "Resume": "resume",
    "LoopStart": "loop_start",
    "LoopEnd": "loop_end",
}


class ParseError(Exception):
    """A fixture file could not be parsed into the estate model."""


def parse_release(paths: list[Path]) -> Estate:
    """Parse one or more .bprelease exports into a single estate model.

    Components appearing in more than one file (the estate export and a
    per-process export share objects and queues) are deduplicated by
    their Blue Prism id; the first occurrence wins.
    """
    files: list[SourceFile] = []
    processes: dict[str, Process] = {}
    objects: dict[str, EstateObject] = {}
    queues: dict[str, Queue] = {}
    unparsed: list[UnparsedElement] = []

    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ParseError(f"{path}: {exc}") from exc
        if root.tag != f"{RELEASE_NS}release":
            raise ParseError(f"{path}: root element is {root.tag}, not a bpr:release")
        files.append(
            SourceFile(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        )
        contents = root.find(f"{RELEASE_NS}contents")
        if contents is None:
            raise ParseError(f"{path}: release has no contents element")
        for child in root:
            if child is not contents and child.tag not in SKIPPED_ELEMENTS:
                unparsed.append(_unparsed(child, str(path), "unrecognized release element"))
        for component in contents:
            # Components live in their own namespaces (process, object,
            # work-queue), not the release namespace.
            tag = component.tag.split("}")[-1]
            if tag == "process":
                process = _parse_process(component, str(path), unparsed)
                processes.setdefault(process.id, process)
            elif tag == "object":
                obj = _parse_object(component, str(path), unparsed)
                objects.setdefault(obj.id, obj)
            elif tag == "work-queue":
                queue = _parse_queue(component)
                queues.setdefault(queue.id, queue)
            elif tag not in ("process-group", "object-group"):
                unparsed.append(_unparsed(component, str(path), "unrecognized release content"))

    return Estate(
        source=EstateSource(files=files, parsed_at=utc_now(), parser_version=PARSER_VERSION),
        processes=list(processes.values()),
        objects=list(objects.values()),
        queues=list(queues.values()),
        unparsed=unparsed,
    )


def _unparsed(element: ET.Element, location: str, note: str) -> UnparsedElement:
    return UnparsedElement(element=element.tag.split("}")[-1], location=location, note=note)


def _parse_queue(component: ET.Element) -> Queue:
    inner = component.find(f"{QUEUE_NS}work-queue")
    attrs = inner.attrib if inner is not None else component.attrib
    max_attempts = attrs.get("max-attempts")
    return Queue(
        id=component.get("id", attrs.get("id", "")),
        name=component.get("name", attrs.get("name", "")),
        key_field=attrs.get("key-field"),
        max_attempts=int(max_attempts) if max_attempts is not None else None,
    )


def _parse_process(
    component: ET.Element, location: str, unparsed: list[UnparsedElement]
) -> Process:
    inner = component.find(f"{PROCESS_NS}process")
    if inner is None:
        raise ParseError(f"{location}: process {component.get('name')!r} has no inner definition")
    stages, data_items, links = _parse_stages(
        inner.findall(f"{PROCESS_NS}stage"), location, unparsed
    )
    for child in inner:
        if child.tag not in SKIPPED_ELEMENTS:
            unparsed.append(_unparsed(child, location, "unrecognized process element"))
    return Process(
        id=component.get("id", ""),
        name=component.get("name", ""),
        description=inner.get("narrative", "").strip(),
        stages=stages,
        data_items=data_items,
        links=links,
        exception_blocks=_resolve_exception_blocks(inner.findall(f"{PROCESS_NS}stage"), stages),
    )


def _parse_object(
    component: ET.Element, location: str, unparsed: list[UnparsedElement]
) -> EstateObject:
    inner = component.find(f"{PROCESS_NS}process")
    if inner is None:
        raise ParseError(f"{location}: object {component.get('name')!r} has no inner definition")
    all_stages = inner.findall(f"{PROCESS_NS}stage")

    # Pages ("subsheets") of type Normal are the object's actions; the
    # page's name lives on its SubSheetInfo stage. The main page
    # (Initialise) and the CleanUp page are Blue Prism lifecycle
    # scaffolding, untouched in the fixtures and deliberately skipped.
    action_sheets = {
        sheet.get("subsheetid")
        for sheet in inner.findall(f"{PROCESS_NS}subsheet")
        if sheet.get("type") == "Normal"
    }
    actions = []
    for sheet_id in action_sheets:
        sheet_stages = [
            stage for stage in all_stages if stage.findtext(f"{PROCESS_NS}subsheetid") == sheet_id
        ]
        name = next(
            (s.get("name", "") for s in sheet_stages if s.get("type") == "SubSheetInfo"),
            sheet_id,
        )
        stages, data_items, _links = _parse_stages(sheet_stages, location, unparsed)
        # ObjectAction has no data_items field; object-page data items
        # are carried as stages of type "data" so nothing is dropped.
        stages.extend(
            Stage(
                id=item.id,
                name=item.name,
                type="data",
                raw_type="Data",
                properties={"data_type": item.data_type, "initial_value": item.initial_value},
            )
            for item in data_items
        )
        actions.append(ObjectAction(id=sheet_id or "", name=name, stages=stages))
    actions.sort(key=lambda a: a.name)
    return EstateObject(id=component.get("id", ""), name=component.get("name", ""), actions=actions)


def _parse_stages(
    stage_elements: list[ET.Element], location: str, unparsed: list[UnparsedElement]
) -> tuple[list[Stage], list[DataItem], list[Link]]:
    stages: list[Stage] = []
    data_items: list[DataItem] = []
    links: list[Link] = []
    loop_groups: dict[str, dict[str, str]] = {}

    for element in stage_elements:
        raw_type = element.get("type", "")
        stage_id = element.get("stageid", "")
        name = element.get("name", "")
        if raw_type in SKIPPED_STAGE_TYPES:
            continue
        if raw_type in ("Data", "Collection"):
            data_items.append(_parse_data_item(element))
            continue

        properties: dict[str, Any] = {}
        if raw_type == "Action":
            stage_type = _parse_action(element, properties)
        elif raw_type in STAGE_TYPE_MAP:
            stage_type = STAGE_TYPE_MAP[raw_type]
            _parse_typed_stage(element, raw_type, properties, loop_groups, stage_id)
        else:
            stage_type = "unknown"
            unparsed.append(
                _unparsed(
                    element, f"{location} stage {name!r}", f"unrecognized stage type {raw_type!r}"
                )
            )

        stages.append(
            Stage(id=stage_id, name=name, type=stage_type, raw_type=raw_type, properties=properties)
        )
        links.extend(_parse_links(element, stage_id))

    for group in loop_groups.values():
        start_id, end_id = group.get("loop_start"), group.get("loop_end")
        by_id = {stage.id: stage for stage in stages}
        if start_id and end_id:
            by_id[start_id].properties["pair_stage_id"] = end_id
            by_id[end_id].properties["pair_stage_id"] = start_id
            by_id[start_id].properties["body_stage_ids"] = _loop_body(start_id, end_id, links)
    return stages, data_items, links


def _parse_data_item(element: ET.Element) -> DataItem:
    initial_value: Any = None
    initial = element.find(f"{PROCESS_NS}initialvalue")
    if element.get("type") == "Collection":
        fields = [
            {"name": f.get("name"), "type": f.get("type")}
            for f in element.findall(f"{PROCESS_NS}collectioninfo/{PROCESS_NS}field")
        ]
        rows = [
            {f.get("name"): f.get("value") for f in row.findall(f"{PROCESS_NS}field")}
            for row in element.findall(f"{PROCESS_NS}initialvalue/{PROCESS_NS}row")
        ]
        initial_value = {"fields": fields, "rows": rows}
    elif initial is not None and (initial.text or "").strip():
        initial_value = initial.text.strip()
    return DataItem(
        id=element.get("stageid", ""),
        name=element.get("name", ""),
        data_type=element.findtext(f"{PROCESS_NS}datatype", "collection").strip(),
        initial_value=initial_value,
    )


def _parse_action(element: ET.Element, properties: dict[str, Any]) -> str:
    resource = element.find(f"{PROCESS_NS}resource")
    obj = resource.get("object", "") if resource is not None else ""
    action = resource.get("action", "") if resource is not None else ""
    inputs = [
        {"name": i.get("name"), "expression": i.get("expr", "")}
        for i in element.findall(f"{PROCESS_NS}inputs/{PROCESS_NS}input")
    ]
    outputs = [
        {"name": o.get("name"), "store_in": o.get("stage", "")}
        for o in element.findall(f"{PROCESS_NS}outputs/{PROCESS_NS}output")
    ]
    properties.update({"object": obj, "action": action, "inputs": inputs, "outputs": outputs})
    if obj == WORK_QUEUES_OBJECT:
        queue_name = next((i["expression"] for i in inputs if i["name"] == "Queue Name"), "").strip(
            '"'
        )
        if queue_name:
            properties["queue_name"] = queue_name
        if action in QUEUE_READ_ACTIONS:
            return "queue_read"
        if action in QUEUE_WRITE_ACTIONS:
            return "queue_write"
    return "action"


def _parse_typed_stage(
    element: ET.Element,
    raw_type: str,
    properties: dict[str, Any],
    loop_groups: dict[str, dict[str, str]],
    stage_id: str,
) -> None:
    if raw_type == "Start":
        properties["inputs"] = [
            {"name": i.get("name"), "type": i.get("type"), "store_in": i.get("stage", "")}
            for i in element.findall(f"{PROCESS_NS}inputs/{PROCESS_NS}input")
        ]
    elif raw_type == "End":
        properties["outputs"] = [
            {"name": o.get("name"), "type": o.get("type"), "from": o.get("stage", "")}
            for o in element.findall(f"{PROCESS_NS}outputs/{PROCESS_NS}output")
        ]
    elif raw_type == "Decision":
        decision = element.find(f"{PROCESS_NS}decision")
        properties["expression"] = decision.get("expression", "") if decision is not None else ""
    elif raw_type == "Calculation":
        calc = element.find(f"{PROCESS_NS}calculation")
        if calc is not None:
            properties["expression"] = calc.get("expression", "")
            properties["store_in"] = calc.get("stage", "")
    elif raw_type == "MultipleCalculation":
        properties["steps"] = [
            {"expression": c.get("expression", ""), "store_in": c.get("stage", "")}
            for c in element.findall(f"{PROCESS_NS}steps/{PROCESS_NS}calculation")
        ]
    elif raw_type == "Note":
        properties["narrative"] = (element.findtext(f"{PROCESS_NS}narrative") or "").strip()
    elif raw_type == "Exception":
        exc = element.find(f"{PROCESS_NS}exception")
        if exc is not None:
            properties["exception_type"] = exc.get("type", "")
            properties["detail"] = exc.get("detail", "")
    elif raw_type in ("LoopStart", "LoopEnd"):
        group_id = (element.findtext(f"{PROCESS_NS}groupid") or "").strip()
        properties["group_id"] = group_id
        if raw_type == "LoopStart":
            properties["loop_type"] = (element.findtext(f"{PROCESS_NS}looptype") or "").strip()
            properties["collection"] = (element.findtext(f"{PROCESS_NS}loopdata") or "").strip()
        loop_groups.setdefault(group_id, {})[STAGE_TYPE_MAP[raw_type]] = stage_id


def _parse_links(element: ET.Element, stage_id: str) -> list[Link]:
    links = []
    for tag, label in (("onsuccess", None), ("ontrue", "true"), ("onfalse", "false")):
        target = (element.findtext(f"{PROCESS_NS}{tag}") or "").strip()
        if target:
            links.append(Link(from_stage=stage_id, to_stage=target, label=label))
    return links


def _loop_body(start_id: str, end_id: str, links: list[Link]) -> list[str]:
    """Stage ids reachable from the loop start without passing its end."""
    outgoing: dict[str, list[str]] = {}
    for link in links:
        outgoing.setdefault(link.from_stage, []).append(link.to_stage)
    body: list[str] = []
    frontier = list(outgoing.get(start_id, []))
    while frontier:
        stage_id = frontier.pop()
        if stage_id == end_id or stage_id in body:
            continue
        body.append(stage_id)
        frontier.extend(outgoing.get(stage_id, []))
    return sorted(body)


def _resolve_exception_blocks(
    stage_elements: list[ET.Element], stages: list[Stage]
) -> list[ExceptionBlock]:
    """Resolve Block stages to the stages they geometrically enclose.

    A Block in the export is only a rectangle: display x/y is its
    top-left corner, w/h its size. Coverage is containment of each
    stage's display point; the Recover stage inside the rectangle is
    the handler exceptions jump to.
    """
    positions: dict[str, tuple[float, float]] = {}
    for element in stage_elements:
        display = element.find(f"{PROCESS_NS}display")
        if display is not None:
            positions[element.get("stageid", "")] = (
                float(display.get("x", "0")),
                float(display.get("y", "0")),
            )

    blocks = []
    by_id = {stage.id: stage for stage in stages}
    for element in stage_elements:
        if element.get("type") != "Block":
            continue
        display = element.find(f"{PROCESS_NS}display")
        x, y = float(display.get("x", "0")), float(display.get("y", "0"))
        w, h = float(display.get("w", "0")), float(display.get("h", "0"))
        covered = [
            stage_id
            for stage_id, (sx, sy) in positions.items()
            if stage_id != element.get("stageid")
            and stage_id in by_id
            and x <= sx <= x + w
            and y <= sy <= y + h
        ]
        handler = next((sid for sid in covered if by_id[sid].type == "recover"), None)
        if handler is None:
            continue
        blocks.append(
            ExceptionBlock(
                id=element.get("stageid", ""),
                covers_stages=sorted(sid for sid in covered if sid != handler),
                handler_stage=handler,
            )
        )
    return blocks
