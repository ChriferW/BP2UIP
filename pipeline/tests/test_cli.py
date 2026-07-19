import json
from pathlib import Path

import pytest

from bp2uip.cli import main

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

STUB_INVOCATIONS = [
    ["extract", "proc-dispute-intake"],
    ["extract", "proc-dispute-intake", "--provider", "openai", "--model", "some-model"],
    ["review", "artifacts/dispute-intake/intent-spec.json"],
    ["review", "artifacts/dispute-intake/intent-spec.json", "--approve", "--by", "Reviewer"],
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
