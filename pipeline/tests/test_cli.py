import json
from pathlib import Path

import pytest

from bp2uip.cli import main
from bp2uip.model import Estate
from bp2uip.provenance import ProvenanceLog
from bp2uip.providers import FakeProvider
from conftest import good_extraction_response

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

STUB_INVOCATIONS = [
    ["generate", "proc-dispute-intake", "--pdd", "--sdd"],
    ["generate", "proc-dispute-intake", "--force"],
    ["report"],
    ["report", "proc-dispute-intake"],
]


@pytest.mark.parametrize("argv", STUB_INVOCATIONS)
def test_stub_subcommands_state_what_they_will_do_and_exit_zero(argv, capsys):
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "not implemented yet" in out
    assert "roadmap week" in out


def test_approve_without_reviewer_identity_is_rejected(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["review", "spec.json", "--approve"])
    assert excinfo.value.code == 2
    assert "never inferred" in capsys.readouterr().err


def test_forced_generation_states_it_is_recorded(capsys):
    main(["generate", "proc-x", "--force"])
    assert "unreviewed generation" in capsys.readouterr().out


def test_parse_writes_estate_json(tmp_path, capsys):
    fixture = FIXTURES / "meridian-p03-address-change.bprelease"
    assert main(["parse", str(fixture), "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "not implemented" not in out
    estate = json.loads((tmp_path / "estate" / "estate.json").read_text(encoding="utf-8"))
    assert [p["name"] for p in estate["processes"]] == ["MFG - Address Change"]
    assert estate["unparsed"] == []


def test_parse_of_missing_file_fails_without_writing(tmp_path, capsys):
    assert main(["parse", "no-such.bprelease", "--out", str(tmp_path)]) == 1
    assert not (tmp_path / "estate").exists()


# --------------------------------------------------------------------------
# extract and review (week 3)
# --------------------------------------------------------------------------


@pytest.fixture
def parsed_out(tmp_path, capsys):
    """A tmp artifact dir holding estate.json parsed from the P03 fixture."""
    fixture = FIXTURES / "meridian-p03-address-change.bprelease"
    assert main(["parse", str(fixture), "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    return tmp_path


def _extract_p03(parsed_out, monkeypatch, responses=None):
    estate_path = parsed_out / "estate" / "estate.json"
    estate = Estate.model_validate_json(estate_path.read_bytes())
    canned = responses if responses is not None else [good_extraction_response(estate)]
    monkeypatch.setattr(
        "bp2uip.cli.get_provider", lambda name=None, model=None: FakeProvider(canned)
    )
    return main(
        [
            "extract",
            "MFG - Address Change",
            "--estate",
            str(estate_path),
            "--out",
            str(parsed_out),
        ]
    )


def test_extract_writes_spec_and_provenance(parsed_out, monkeypatch, capsys):
    assert _extract_p03(parsed_out, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "not implemented" not in out
    spec_dir = parsed_out / "mfg-address-change"
    spec = json.loads((spec_dir / "intent-spec.json").read_text(encoding="utf-8"))
    assert spec["status"] == "draft"
    assert spec["approval"] is None
    assert spec["extraction"]["provider"] == "fake"
    log = ProvenanceLog.open(spec_dir / "provenance.jsonl", spec["process_id"])
    assert log.verify()
    assert [e.event for e in log.events()] == ["extraction_run", "spec_drafted"]
    # The derived markdown view is written next to the JSON, with
    # citations resolved to stage names rather than raw ids.
    markdown = (spec_dir / "intent-spec.md").read_text(encoding="utf-8")
    assert "# Intent spec: MFG - Address Change" in markdown
    assert spec["purpose"]["citations"][0] not in markdown


def test_extract_without_estate_document_fails(tmp_path, capsys):
    missing = tmp_path / "estate" / "estate.json"
    assert main(["extract", "P03", "--estate", str(missing), "--out", str(tmp_path)]) == 1
    assert "run `bp2uip parse` first" in capsys.readouterr().out


def test_extract_fails_cleanly_on_bad_provider_output(parsed_out, monkeypatch, capsys):
    assert _extract_p03(parsed_out, monkeypatch, responses=["nope", "still nope"]) == 1
    assert "after one retry" in capsys.readouterr().out
    assert not (parsed_out / "mfg-address-change").exists()


def test_review_displays_spec_with_citations(parsed_out, monkeypatch, capsys):
    assert _extract_p03(parsed_out, monkeypatch) == 0
    capsys.readouterr()
    spec_path = parsed_out / "mfg-address-change" / "intent-spec.json"
    assert main(["review", str(spec_path)]) == 0
    out = capsys.readouterr().out
    assert "[draft]" in out
    assert "BR-1" in out
    assert "cites:" in out
    assert "not yet approved" in out


def test_review_approve_writes_approved_spec_and_provenance(parsed_out, monkeypatch, capsys):
    assert _extract_p03(parsed_out, monkeypatch) == 0
    spec_path = parsed_out / "mfg-address-change" / "intent-spec.json"
    assert main(["review", str(spec_path), "--approve", "--by", "Chris Williams"]) == 0
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["status"] == "approved"
    assert spec["approval"]["approved_by"] == "Chris Williams"
    log = ProvenanceLog.open(spec_path.parent / "provenance.jsonl", spec["process_id"])
    assert log.verify()
    assert [e.event for e in log.events()] == [
        "extraction_run",
        "spec_drafted",
        "spec_approved",
    ]
    markdown = (spec_path.parent / "intent-spec.md").read_text(encoding="utf-8")
    assert "**approved**" in markdown
    assert "Approved by: **Chris Williams**" in markdown
    # Approving twice is refused.
    assert main(["review", str(spec_path), "--approve", "--by", "Chris Williams"]) == 1
    assert "already approved" in capsys.readouterr().out


def test_review_of_missing_spec_fails(tmp_path, capsys):
    assert main(["review", str(tmp_path / "nope.json")]) == 1
    assert "not found" in capsys.readouterr().out


# --------------------------------------------------------------------------
# analyze (week 4)
# --------------------------------------------------------------------------


def _analyze(parsed_out, process=None):
    argv = ["analyze", "--estate", str(parsed_out / "estate" / "estate.json")]
    argv += ["--out", str(parsed_out)]
    if process:
        argv.insert(1, process)
    return main(argv)


def test_analyze_writes_estate_analysis_and_uplift(parsed_out, monkeypatch, capsys):
    assert _extract_p03(parsed_out, monkeypatch) == 0
    capsys.readouterr()
    assert _analyze(parsed_out) == 0
    out = capsys.readouterr().out
    assert "not implemented" not in out

    analysis = json.loads((parsed_out / "estate" / "analysis.json").read_text(encoding="utf-8"))
    assert [c["process_name"] for c in analysis["complexity"]] == ["MFG - Address Change"]
    assert analysis["complexity"][0]["band"] == "low"

    spec_dir = parsed_out / "mfg-address-change"
    report = json.loads((spec_dir / "uplift.json").read_text(encoding="utf-8"))
    assert report["spec_ref"]["status_at_analysis"] == "draft"
    assert report["criteria_version"]
    assert report["findings"]
    log = ProvenanceLog.open(spec_dir / "provenance.jsonl", report["process_id"])
    assert log.verify()
    assert [e.event for e in log.events()] == [
        "extraction_run",
        "spec_drafted",
        "uplift_analyzed",
    ]
    markdown = (spec_dir / "uplift.md").read_text(encoding="utf-8")
    assert "# Uplift analysis: MFG - Address Change" in markdown
    assert report["findings"][0]["stage_ids"][0] not in markdown


def test_analyze_without_estate_document_fails(tmp_path, capsys):
    missing = tmp_path / "estate" / "estate.json"
    assert main(["analyze", "--estate", str(missing), "--out", str(tmp_path)]) == 1
    assert "run `bp2uip parse` first" in capsys.readouterr().out


def test_analyze_skips_processes_without_specs(parsed_out, capsys):
    # No spec extracted: estate-wide analysis still writes complexity
    # and the dependency graph, and says why uplift was skipped.
    assert _analyze(parsed_out) == 0
    out = capsys.readouterr().out
    assert "uplift analysis skipped" in out
    assert (parsed_out / "estate" / "analysis.json").exists()
    assert not (parsed_out / "mfg-address-change" / "uplift.json").exists()


def test_analyze_named_process_without_spec_fails(parsed_out, capsys):
    assert _analyze(parsed_out, process="MFG - Address Change") == 1
    assert "uplift analysis skipped" in capsys.readouterr().out
