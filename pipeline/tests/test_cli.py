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
    # Approving twice is refused.
    assert main(["review", str(spec_path), "--approve", "--by", "Chris Williams"]) == 1
    assert "already approved" in capsys.readouterr().out


def test_review_of_missing_spec_fails(tmp_path, capsys):
    assert main(["review", str(tmp_path / "nope.json")]) == 1
    assert "not found" in capsys.readouterr().out
