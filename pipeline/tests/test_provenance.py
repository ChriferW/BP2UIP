from bp2uip.provenance import ProvenanceLog


def _append_three(log: ProvenanceLog) -> None:
    log.append(actor="tester", event="parsed", detail={"files": 1})
    log.append(actor="tester", event="spec_drafted", detail={"spec_id": "spec-test-001"})
    log.append(actor="reviewer", event="spec_approved", detail={"spec_id": "spec-test-001"})


def test_append_creates_one_line_per_event(log):
    _append_three(log)
    lines = log.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_sequence_numbers_are_contiguous(log):
    _append_three(log)
    assert [e.seq for e in log.events()] == [1, 2, 3]


def test_first_event_has_null_prev_hash_and_chain_links(log):
    _append_three(log)
    events = log.events()
    assert events[0].prev_hash is None
    assert all(e.prev_hash for e in events[1:])


def test_append_preserves_prior_lines_byte_for_byte(log):
    log.append(actor="tester", event="parsed")
    before = log.path.read_bytes()
    log.append(actor="tester", event="spec_drafted")
    after = log.path.read_bytes()
    assert after.startswith(before)


def test_verify_passes_on_untampered_log(log):
    _append_three(log)
    reopened = ProvenanceLog.open(log.path, "proc-test")
    assert reopened.verify() is True


def test_verify_fails_when_a_line_is_altered(log):
    _append_three(log)
    lines = log.path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace("spec_drafted", "spec_approved")
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert ProvenanceLog.open(log.path, "proc-test").verify() is False


def test_verify_fails_when_a_line_is_removed(log):
    _append_three(log)
    lines = log.path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert ProvenanceLog.open(log.path, "proc-test").verify() is False


def test_empty_log_verifies(log):
    assert log.verify() is True
