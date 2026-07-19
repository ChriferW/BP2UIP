"""The bp2uip command line interface.

`parse` is implemented (roadmap week 2). Every other subcommand is
still a stub: it parses its arguments, states what it will do and
which roadmap week implements it, and exits 0. No fake output, no
fake progress.
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from bp2uip.model import to_document
from bp2uip.parser import ParseError, parse_release


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


def _cmd_extract(args: argparse.Namespace) -> int:
    provider = args.provider or "anthropic (default, or BP2UIP_PROVIDER)"
    print(
        f"extract: not implemented yet (roadmap week 3). Will extract a draft "
        f"intent spec for process '{args.process}' via provider {provider} "
        f"and write it under artifacts/."
    )
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    if args.approve:
        print(
            f"review: not implemented yet (roadmap week 3). Will approve spec "
            f"'{args.spec}' as reviewed by '{args.by}', record a spec_approved "
            f"event to provenance, and write the approved spec."
        )
    else:
        print(
            f"review: not implemented yet (roadmap week 3). Will display spec "
            f"'{args.spec}' with its source stage citations for review."
        )
    return 0


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
    p.set_defaults(func=_cmd_extract)

    p = sub.add_parser("review", help="review or approve an intent spec")
    p.add_argument("spec", help="path to the intent spec")
    p.add_argument("--approve", action="store_true", help="approve the spec")
    p.add_argument("--by", help="reviewer name; required with --approve, never inferred")
    p.set_defaults(func=_cmd_review)

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
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "review" and args.approve and not args.by:
        parser.error("--approve requires --by: approval identity is never inferred")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
