import json
from dataclasses import replace

from blindspot.assessment import assess
from blindspot.models import Protocol
from blindspot.nasa import research_context
from blindspot.sessions import Session, compare
from blindspot.storage import SessionStore
from blindspot.synthetic import make_demo

P = Protocol()


def session(scenario="clean", source="webcam", who="P01", when=100):
    result = assess(make_demo(scenario), P, 15)
    return Session.create(who, source, P, result, when)


def test_three_eligible_prior_sessions_enable_comparison():
    old = [session(when=i) for i in [10, 20, 30]]
    result = compare(session(), old, P)
    assert result.status == "comparable"
    assert result.baseline_hz == 2
    assert result.change_percent == 0
    assert result.baseline_ids == tuple(s.id for s in old)


def test_invalid_synthetic_other_person_future_and_stale_sessions_are_excluded():
    candidates = [
        session(source="synthetic"),
        session(who="other"),
        session("tracking_loss"),
        session(when=200),
        session(when=-4_000_000),
    ]
    result = compare(session(), candidates, P)
    assert result.status == "baseline_needed"
    assert result.baseline_ids == ()


def test_protocol_and_hand_changes_require_a_new_baseline():
    candidates = [replace(session(when=i), protocol_id="other") for i in [10, 20, 30]]
    assert compare(session(), candidates, P).status == "baseline_needed"


def test_bad_current_session_never_gets_a_performance_claim():
    result = compare(session("stale_stream"), [session(when=i) for i in [10, 20, 30]], P)
    assert result.status == "insufficient_evidence"
    assert result.change_percent is None


def test_zero_baseline_does_not_divide_by_zero():
    s = session()
    zero = replace(s.assessment, rate_hz=0, count=0)
    old = [replace(session(when=i), assessment=zero) for i in [10, 20, 30]]
    result = compare(s, old, P)
    assert result.change_percent is None
    assert result.baseline_hz == 0


def test_duplicate_baselines_cannot_satisfy_minimum():
    old = session(when=10)
    assert compare(session(), [old, old, old], P).status == "baseline_needed"


def test_sqlite_roundtrip_receipt_and_idempotent_save(tmp_path):
    s = session()
    with SessionStore(tmp_path / "sessions.db") as store:
        store.save(s)
        store.save(s)
        loaded = store.recent()
        assert loaded == [s]
        assert store.get(s.id) == s
    receipt = s.receipt(compare(s, [], P), P)
    assert receipt["research_context"]["role"] == "research_context_only"
    assert receipt["source"] == "webcam"
    assert receipt["policy"]["min_coverage"] == 0.8
    assert json.loads(json.dumps(receipt, allow_nan=False))["assessment"]["count"] == 30


def test_storage_is_paginated_and_preserves_missing_rate(tmp_path):
    with SessionStore(tmp_path / "sessions.db") as store:
        missing = replace(session(), assessment=assess([], P, 15))
        store.save(missing)
        store.save(session(when=200))
        assert len(store.recent(limit=1, offset=1)) == 1
        assert store.count() == 2
        assert store.get(missing.id).assessment.rate_hz is None


def test_nasa_adapter_includes_official_source_and_limitations():
    context = research_context()
    assert context["url"].startswith("https://www.nasa.gov/")
    assert len(context["content_sha256"]) == 64
    assert context["role"] == "research_context_only"


def test_saved_receipt_is_frozen_on_repeated_save(tmp_path):
    s = session()
    original = s.receipt(compare(s, [], P), P)
    with SessionStore(tmp_path / "sessions.db") as store:
        store.save(s, original)
        store.save(s, {"replacement": True})
        assert store.receipt(s.id) == json.loads(json.dumps(original))
