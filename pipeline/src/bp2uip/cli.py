"""The bp2uip command line interface.

`parse` (roadmap week 2), `extract`, `review` (roadmap week 3), and
`analyze` (roadmap week 4) are implemented. Every other subcommand is
still a stub: it parses its
arguments, states what it will do and which roadmap week implements
it, and exits 0. No fake output, no fake progress.
"""

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from bp2uip.analysis import analyze_estate, analyze_uplift
from bp2uip.intent import ExtractionError, approve_spec, extract_intent, find_process
from bp2uip.model import Estate, EstateRef, IntentSpec, to_document
from bp2uip.parser import ParseError, parse_release
from bp2uip.provenance import ProvenanceLog
from bp2uip.providers import ProviderConfigError, get_provider
from bp2uip.render import spec_to_markdown, uplift_to_markdown


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        estate = parse_release([Path(p) for p in args.fixtures])
    except ParseError as exc:
        print(f"parse: {exc}")
        return 1
    out_path = Path(args.out) / "estate" / "estate.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(to_document(estate), indent=2) + "\n", encoding="utf-8")
    print(
        f"parse: {len(estate.processes)} process(es), {len(estate.objects)} object(s), "
        f"{len(estate.queues)} queue(s) from {len(estate.source.files)} file(s) "
        f"-> {out_path}"
    )
    if estate.unparsed:
        print(f"parse: {len(estate.unparsed)} unparsed element(s) recorded in the estate model:")
        for entry in estate.unparsed:
            print(f"  {entry.element} at {entry.location}: {entry.note}")
    return 0


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _cmd_extract(args: argparse.Namespace) -> int:
    estate_path = Path(args.estate)
    if not estate_path.exists():
        print(f"extract: estate document not found at {estate_path}; run `bp2uip parse` first")
        return 1
    raw = estate_path.read_bytes()
    estate = Estate.model_validate_json(raw)
    estate_ref = EstateRef(path=str(estate_path), sha256=hashlib.sha256(raw).hexdigest())
    try:
        provider = get_provider(args.provider, model=args.model)
        spec = extract_intent(estate, args.process, provider, estate_ref=estate_ref)
    except (ProviderConfigError, ExtractionError) as exc:
        print(f"extract: {exc}")
        return 1
    process = find_process(estate, args.process)
    out_dir = Path(args.out) / _slug(process.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / "intent-spec.json"
    spec_path.write_text(json.dumps(to_document(spec), indent=2) + "\n", encoding="utf-8")
    (out_dir / "intent-spec.md").write_text(spec_to_markdown(spec, estate), encoding="utf-8")
    log = ProvenanceLog.open(out_dir / "provenance.jsonl", process.id)
    log.append(
        actor=f"bp2uip/{provider.name}",
        event="extraction_run",
        detail={
            "provider": spec.extraction.provider,
            "model": spec.extraction.model,
            "prompt_version": spec.extraction.prompt_version,
        },
    )
    log.append(
        actor=f"bp2uip/{provider.name}",
        event="spec_drafted",
        detail={"spec_id": spec.spec_id, "path": str(spec_path)},
    )
    print(
        f"extract: draft spec {spec.spec_id} for '{process.name}' "
        f"({spec.extraction.provider}/{spec.extraction.model}, "
        f"prompt v{spec.extraction.prompt_version}) -> {spec_path}"
    )
    print(f"extract: review it with `bp2uip review {spec_path}`")
    return 0


def _print_cited(indent: str, citations: list[str]) -> None:
    print(f"{indent}cites: {', '.join(citations)}")


def _cmd_review(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"review: spec not found at {spec_path}")
        return 1
    spec = IntentSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))

    if args.approve:
        log = ProvenanceLog.open(spec_path.parent / "provenance.jsonl", spec.process_id)
        try:
            approved = approve_spec(spec, approved_by=args.by, log=log)
        except ValueError as exc:
            print(f"review: {exc}")
            return 1
        spec_path.write_text(json.dumps(to_document(approved), indent=2) + "\n", encoding="utf-8")
        # Refresh the derived markdown view. Stage names need the estate;
        # if it is gone, the rendering falls back to raw ids.
        estate_path = Path(approved.estate_ref.path)
        estate = (
            Estate.model_validate_json(estate_path.read_bytes()) if estate_path.exists() else None
        )
        (spec_path.parent / "intent-spec.md").write_text(
            spec_to_markdown(approved, estate), encoding="utf-8"
        )
        print(f"review: spec {approved.spec_id} approved by {args.by} -> {spec_path}")
        return 0

    print(f"spec {spec.spec_id} for process {spec.process_id} [{spec.status}]")
    print(
        f"extracted by {spec.extraction.provider}/{spec.extraction.model} "
        f"(prompt v{spec.extraction.prompt_version})"
    )
    print(f"\npurpose: {spec.purpose.text}")
    _print_cited("  ", spec.purpose.citations)
    print("\ninputs:")
    for item in spec.inputs:
        source = f" (from {item.source})" if item.source else ""
        print(f"  - {item.name}: {item.description}{source}")
        _print_cited("    ", item.citations)
    print("\noutputs:")
    for item in spec.outputs:
        destination = f" (to {item.destination})" if item.destination else ""
        print(f"  - {item.name}: {item.description}{destination}")
        _print_cited("    ", item.citations)
    print("\nbusiness rules:")
    for rule in spec.business_rules:
        print(f"  - {rule.id}: {rule.statement}")
        _print_cited("    ", rule.citations)
    print("\nexception semantics:")
    for semantic in spec.exception_semantics:
        print(f"  - when {semantic.condition}: {semantic.current_handling}")
        _print_cited("    ", semantic.citations)
    print("\nhuman touchpoints:")
    for touchpoint in spec.human_touchpoints:
        print(f"  - {touchpoint.description}")
        _print_cited("    ", touchpoint.citations)
    if spec.approval:
        print(f"\napproved by {spec.approval.approved_by} at {spec.approval.approved_at}")
    else:
        print("\nnot yet approved; approve with --approve --by <reviewer>")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    estate_path = Path(args.estate)
    if not estate_path.exists():
        print(f"analyze: estate document not found at {estate_path}; run `bp2uip parse` first")
        return 1
    raw = estate_path.read_bytes()
    estate = Estate.model_validate_json(raw)
    estate_ref = EstateRef(path=str(estate_path), sha256=hashlib.sha256(raw).hexdigest())
    out = Path(args.out)

    analysis = analyze_estate(estate, estate_ref=estate_ref)
    analysis_path = out / "estate" / "analysis.json"
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.write_text(json.dumps(to_document(analysis), indent=2) + "\n", encoding="utf-8")
    print(
        f"analyze: complexity and dependency graph for "
        f"{len(estate.processes)} process(es) -> {analysis_path}"
    )
    for entry in analysis.complexity:
        print(f"  {entry.process_name}: score {entry.score} ({entry.band})")

    if args.process:
        try:
            targets = [find_process(estate, args.process)]
        except ExtractionError as exc:
            print(f"analyze: {exc}")
            return 1
    else:
        targets = estate.processes

    failed = False
    for process in targets:
        spec_path = out / _slug(process.name) / "intent-spec.json"
        if not spec_path.exists():
            print(
                f"analyze: no intent spec for '{process.name}' at {spec_path}; "
                f"run `bp2uip extract` first (uplift analysis skipped)"
            )
            # Skipping the whole estate's stragglers is routine; failing
            # to analyze the one process the user named is an error.
            failed = failed or bool(args.process)
            continue
        spec = IntentSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
        stale = spec.estate_ref.sha256 != estate_ref.sha256
        if stale:
            print(
                f"analyze: warning: spec {spec.spec_id} was extracted from a "
                f"different estate revision (sha mismatch); findings may not "
                f"line up with the current stages"
            )
        report = analyze_uplift(estate, spec)
        report_path = spec_path.parent / "uplift.json"
        report_path.write_text(json.dumps(to_document(report), indent=2) + "\n", encoding="utf-8")
        (spec_path.parent / "uplift.md").write_text(
            uplift_to_markdown(report, estate), encoding="utf-8"
        )
        detail = {
            "spec_id": spec.spec_id,
            "status_at_analysis": report.spec_ref.status_at_analysis,
            "criteria_version": report.criteria_version,
            "path": str(report_path),
        }
        if stale:
            detail["estate_sha_mismatch"] = True
        log = ProvenanceLog.open(spec_path.parent / "provenance.jsonl", process.id)
        log.append(actor="bp2uip/analyzer", event="uplift_analyzed", detail=detail)
        counts: dict[str, int] = {}
        for finding in report.findings:
            counts[finding.classification] = counts.get(finding.classification, 0) + 1
        summary = ", ".join(f"{n} {c}" for c, n in sorted(counts.items()))
        print(
            f"analyze: uplift for '{process.name}' "
            f"(spec {report.spec_ref.status_at_analysis}): {summary} -> {report_path}"
        )
    return 1 if failed else 0


def _cmd_generate(args: argparse.Namespace) -> int:
    targets = [
        name
        for name, wanted in [
            ("pdd", args.pdd),
            ("sdd", args.sdd),
            ("xaml", args.xaml),
            ("bpmn", args.bpmn),
        ]
        if wanted
    ] or ["pdd", "sdd"]
    forced = (
        " --force is set: the run would be recorded in provenance as an unreviewed generation."
        if args.force
        else ""
    )
    print(
        f"generate: not implemented yet (roadmap weeks 5-7). Will generate "
        f"{', '.join(targets)} for process '{args.process}' from its approved "
        f"intent spec; refuses to run on a draft.{forced}"
    )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    scope = f"process '{args.process}'" if args.process else "the whole estate"
    print(
        f"report: not implemented yet (roadmap week 5). Will generate the "
        f"modernization report for {scope}: complexity, uplift findings, "
        f"migration recommendation."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bp2uip",
        description="Migration compiler: Blue Prism release exports in, "
        "UiPath artifacts out, with provenance.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse", help="parse .bprelease exports into the estate model")
    p.add_argument("fixtures", nargs="+", help=".bprelease file(s)")
    p.add_argument("-o", "--out", default="artifacts", help="artifact output directory")
    p.set_defaults(func=_cmd_parse)

    p = sub.add_parser("extract", help="extract a draft intent spec for one process")
    p.add_argument("process", help="process ID or name")
    p.add_argument("--provider", help="LLM provider (overrides BP2UIP_PROVIDER)")
    p.add_argument("--model", help="model override; the exact string is recorded in the spec")
    p.add_argument(
        "--estate",
        default="artifacts/estate/estate.json",
        help="estate document produced by `bp2uip parse`",
    )
    p.add_argument("-o", "--out", default="artifacts", help="artifact output directory")
    p.set_defaults(func=_cmd_extract)

    p = sub.add_parser("review", help="review or approve an intent spec")
    p.add_argument("spec", help="path to the intent spec")
    p.add_argument("--approve", action="store_true", help="approve the spec")
    p.add_argument("--by", help="reviewer name; required with --approve, never inferred")
    p.set_defaults(func=_cmd_review)

    p = sub.add_parser(
        "analyze",
        help="complexity, dependency graph, and uplift findings from the estate and its specs",
    )
    p.add_argument("process", nargs="?", help="limit uplift analysis to one process (ID or name)")
    p.add_argument(
        "--estate",
        default="artifacts/estate/estate.json",
        help="estate document produced by `bp2uip parse`",
    )
    p.add_argument("-o", "--out", default="artifacts", help="artifact output directory")
    p.set_defaults(func=_cmd_analyze)

    p = sub.add_parser("generate", help="generate documents and UiPath artifacts")
    p.add_argument("process", help="process ID or name")
    p.add_argument("--pdd", action="store_true", help="as-is process design document")
    p.add_argument("--sdd", action="store_true", help="to-be solution design document")
    p.add_argument("--xaml", action="store_true", help="REFramework .xaml scaffolding")
    p.add_argument("--bpmn", action="store_true", help="Maestro BPMN")
    p.add_argument(
        "--force",
        action="store_true",
        help="generate from an unapproved spec; recorded in provenance as an unreviewed generation",
    )
    p.set_defaults(func=_cmd_generate)

    p = sub.add_parser("report", help="generate the modernization report")
    p.add_argument("process", nargs="?", help="limit to one process")
    p.set_defaults(func=_cmd_report)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Populate the environment from a local gitignored .env if one
    # exists (searched upward from the current directory). The code
    # itself still only ever reads environment variables; a variable
    # already set in the environment wins over the file.
    load_dotenv(find_dotenv(usecwd=True))
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "review" and args.approve and not args.by:
        parser.error("--approve requires --by: approval identity is never inferred")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
