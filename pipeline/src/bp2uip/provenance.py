"""Append-only migration provenance log, one JSONL file per process.

Events are never edited or deleted; corrections are new events. Each
line carries the sha256 of the previous line's exact bytes, so any
alteration or removal of history is detectable with verify().
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from bp2uip.model import SCHEMA_VERSION, EventType, ProvenanceEvent, to_document, utc_now


class ProvenanceIntegrityError(Exception):
    """The log's hash chain or sequence numbering does not hold."""


def _serialize(event: ProvenanceEvent) -> str:
    return json.dumps(to_document(event), separators=(",", ":"), sort_keys=True)


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


class ProvenanceLog:
    def __init__(self, path: Path, process_id: str, lines: list[str]) -> None:
        self.path = path
        self.process_id = process_id
        self._lines = lines

    @classmethod
    def open(cls, path: Path, process_id: str) -> "ProvenanceLog":
        """Open an existing log or start a new one for a process."""
        lines: list[str] = []
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
        return cls(path, process_id, lines)

    def events(self) -> list[ProvenanceEvent]:
        return [ProvenanceEvent.model_validate_json(line) for line in self._lines]

    def append(
        self, *, actor: str, event: EventType, detail: dict[str, Any] | None = None
    ) -> ProvenanceEvent:
        """Append one event. The only write operation the log supports."""
        prev = self._lines[-1] if self._lines else None
        record = ProvenanceEvent(
            schema_version=SCHEMA_VERSION,
            process_id=self.process_id,
            seq=len(self._lines) + 1,
            prev_hash=_line_hash(prev) if prev is not None else None,
            timestamp=utc_now(),
            actor=actor,
            event=event,
            detail=detail or {},
        )
        line = _serialize(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        self._lines.append(line)
        return record

    def verify(self) -> bool:
        """True if sequence numbers are contiguous and the hash chain holds."""
        prev: str | None = None
        for i, line in enumerate(self._lines, start=1):
            try:
                record = ProvenanceEvent.model_validate_json(line)
            except ValueError:
                return False
            expected = _line_hash(prev) if prev is not None else None
            if record.seq != i or record.prev_hash != expected:
                return False
            if record.process_id != self.process_id:
                return False
            prev = line
        return True
