import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from blindspot.lab import run_lab

ROOT = Path(__file__).resolve().parents[1]


def test_all_faults_retain_same_reference_but_block_comparison():
    for fault in ["tracking_loss", "stale_stream", "low_confidence", "replayed_frames"]:
        session, _, comparison, receipt, _ = run_lab(fault)
        assert session.assessment.count < 30
        assert comparison.status == "insufficient_evidence"
        assert len(receipt["lab_reference_sessions"]) == 3
        assert receipt["source"] == "synthetic"


def test_clean_lab_is_comparable():
    assert run_lab("clean")[2].change_percent == 0


def test_dashboard_renders_empty_and_demo_success(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_DB", str(tmp_path / "test.db"))
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=20)
    assert not app.exception
    assert any("No saved sessions" in e.value for e in app.info)
    next(b for b in app.button if b.label == "Run fault demonstration").click().run()
    assert not app.exception
    assert any("Insufficient evidence" in e.value for e in app.warning)
    next(b for b in app.button if b.label == "Save session").click().run()
    assert not app.exception
    assert any("Session saved" in e.value for e in app.success)


def test_receipt_is_json_safe_and_explicit_about_no_video():
    receipt = run_lab("stale_stream")[3]
    assert json.loads(json.dumps(receipt, allow_nan=False))["raw_video_stored"] is False


def test_theme_mapping():
    import re

    import tomllib

    theme = tomllib.loads((ROOT / ".streamlit/config.toml").read_text())["theme"]
    css = (ROOT / "blindspot/assets/theme.css").read_text()
    for target, source in [
        ("primaryColor", "primary"),
        ("backgroundColor", "background"),
        ("secondaryBackgroundColor", "surface"),
        ("textColor", "text"),
    ]:
        value = re.search(rf"--bs-{source}: (#[0-9a-f]+)", css)[1]
        assert theme[target] == value
        assert value in (ROOT / "DESIGN.md").read_text()
