"""Run against a local Streamlit server: python tests/browser_check.py [URL]."""

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8501"
ARTIFACTS = Path(os.environ.get("BLINDSPOT_BROWSER_ARTIFACTS", "verification/browser"))
ARTIFACTS.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"),
        headless=True,
        args=["--no-sandbox"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )
    page.goto(URL)
    page.get_by_role("heading", name="Can we trust this measurement?").wait_for()
    page.get_by_role("tab", name="Fault lab").click()
    panel = page.get_by_role("tabpanel", name="Fault lab")
    panel.get_by_role("button", name="Run fault demonstration").click()
    panel.get_by_text("Insufficient evidence.", exact=False).first.wait_for()
    # Regression: Streamlit's HTML sanitizer removes inline SVG. The real trace must render.
    image = panel.get_by_role("img", name="Hand movement and usable tracking over time")
    image.wait_for()
    assert image.evaluate("(node) => node.complete && node.naturalWidth > 0")
    assert panel.get_by_text("67%", exact=True).is_visible()
    page.screenshot(path=str(ARTIFACTS / "fault-lab.png"), full_page=True)
    with page.expect_download() as download:
        panel.get_by_role("button", name="Download evidence receipt").click()
    data = json.loads(Path(download.value.path()).read_text())
    assert data["comparison"]["status"] == "insufficient_evidence"
    assert data["assessment"]["count"] == 20
    panel.get_by_role("button", name="Save session", exact=True).click()
    panel.get_by_text("Session saved.", exact=False).wait_for()
    panel.get_by_text("Clean tracking", exact=True).click()
    panel.get_by_role("button", name="Run fault demonstration").click()
    panel.get_by_text("Observed tapping rate matches", exact=False).wait_for()
    assert panel.get_by_text("30", exact=True).is_visible()
    page.get_by_role("tab", name="Session log").click()
    page.get_by_role("tabpanel", name="Session log").get_by_text("Showing", exact=False).wait_for()
    page.get_by_role("tab", name="Research").click()
    assert page.get_by_role("link", name="NASA Human System Risks: Sensorimotor Risk").is_visible()
    page.get_by_role("tab", name="Assessment").click()
    # A real local camera is optional; only test the safe unavailable-camera path here.
    page.get_by_label("Camera index").fill("9")
    page.get_by_label("Camera index").press("Enter")
    page.get_by_role("button", name="Start 15-second assessment").click()
    page.get_by_text("Cannot open camera.", exact=False).wait_for(timeout=20000)
    # Keyboard navigation and responsive sibling screen.
    page.get_by_label("Participant code", exact=True).focus()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement !== document.body")
    page.set_viewport_size({"width": 390, "height": 844})
    page.emulate_media(reduced_motion="reduce")
    page.get_by_role("tab", name="Fault lab").click()
    page.screenshot(path=str(ARTIFACTS / "fault-lab-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    scrollbar = page.evaluate("getComputedStyle(document.documentElement).scrollbarColor")
    assert scrollbar != "auto"
    assert not errors, errors
    (ARTIFACTS / "report.json").write_text(
        json.dumps(
            {
                "browser": browser.version,
                "viewports": ["1440x1100", "390x844"],
                "page_errors": errors,
                "downloaded_receipt": "verified",
                "flows": [
                    "fault",
                    "clean",
                    "save",
                    "history",
                    "research",
                    "camera unavailable",
                    "keyboard focus",
                    "reduced motion",
                    "narrow layout",
                ],
                "scrollbar": scrollbar,
            },
            indent=2,
        )
    )
    print("Browser checks passed")
    browser.close()
