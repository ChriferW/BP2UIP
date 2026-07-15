"""Front-end: .bprelease XML in, platform-neutral estate model out.

This is the only module that reads Blue Prism formats. The
implementation is built against the real fixture exports in fixtures/
(roadmap weeks 1 and 2); no structure of the .bprelease format is
assumed before those land.
"""

from pathlib import Path

from bp2uip.model import Estate


class ParseError(Exception):
    """A fixture file could not be parsed into the estate model."""


def parse_release(paths: list[Path]) -> Estate:
    """Parse one or more .bprelease exports into a single estate model.

    Contract (see docs/master-plan.md sections 2.1 and 3):
    every stage keeps its verbatim raw_type string, and any element the
    parser does not understand is recorded in Estate.unparsed rather
    than silently dropped.
    """
    raise NotImplementedError(
        "parser is implemented against the real fixture exports (roadmap week 2); "
        "no .bprelease structure is assumed before fixtures land"
    )
