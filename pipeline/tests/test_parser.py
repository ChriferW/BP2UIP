"""Parser tests are keyed to the fixture feature matrix in
docs/master-plan.md section 5. Until the real .bprelease exports land
in fixtures/ (roadmap week 1), the matrix cases are skipped
placeholders and the only assertion is that the stub is honest."""

from pathlib import Path

import pytest

from bp2uip.parser import parse_release

FIXTURE_FEATURES = [
    "decision tree: decision stages parsed with all outgoing links and labels",
    "calculation block: calculation stage with expression captured in properties",
    "loop: loop start/end pairing and body membership",
    "exception block: covered stages and handler resolved",
    "sub-object call: cross-reference from process stage to object action",
    "queue interaction: queue read/write stages linked to a named queue",
    "whole estate: every fixture parses with zero undocumented unparsed entries",
]


def test_parse_release_is_an_honest_stub():
    with pytest.raises(NotImplementedError):
        parse_release([Path("fixtures/does-not-exist.bprelease")])


@pytest.mark.parametrize("feature", FIXTURE_FEATURES)
@pytest.mark.skip(reason="parser is built against real fixture exports (roadmap weeks 1-2)")
def test_parser_fixture_matrix(feature):
    raise AssertionError("placeholder; implemented when fixtures land")
