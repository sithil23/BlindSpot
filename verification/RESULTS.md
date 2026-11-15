# Delivery verification

Verified on 14 November 2026, Linux x86_64, Python 3.12.

- `python -m pytest -q`: **32 passed**. Includes state transitions, tracking loss,
  packet gaps, replay, stream expiry without new input, malformed data, valid-session
  baselines, source separation, zero baseline, SQLite roundtrip/idempotency and UI flows.
- `ruff check .`: passed.
- `ruff format --check .`: 26 files formatted.
- `mypy blindspot`: no issues in 15 source files.
- `python -m build`: source distribution and wheel built successfully in isolated environments.
- Wheel inspection: CSS and offline NASA research note included.
- Frontend premium static audit: zero findings (`premium-audit.json`). This audit inspects
  contracts and selected source patterns; it is not a full accessibility certification.
- Chromium runtime checks: fault and clean cases, rendered chart, JSON receipt download,
  explicit save, history, research source link, unavailable-camera recovery, keyboard focus,
  reduced motion and 390px viewport. No browser page errors or console errors observed.
  See `browser/report.json` and screenshots.
- Real MediaPipe model loaded and processed a 640×480 blank RGB frame on CPU, returning
  zero hands. This environment lacked `libGLESv2.so.2`; a distribution library was extracted
  inside the temporary workspace for this check. No operating-system packages were changed.
  MediaPipe emitted upstream inference feedback/projection warnings on stderr.
- Model SHA256 verified against the versioned Google download:
  `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`.
- Dependency versions exercised: Streamlit 1.67.0, MediaPipe 0.10.35, OpenCV runtime 4.14.0.
- Command-line tracking-loss demonstration: 20 observed cycles, 67% coverage, 5-second
  tracking gap, insufficient evidence. The clean case has 30 cycles.

## Remaining verification

No physical webcam was available. Live human hand detection, handedness, camera latency,
movement-count accuracy and repeatability must be rehearsed on the target computer.
The synthetic tests do not establish medical or spaceflight validity. A full assistive-
technology audit and cross-platform camera testing were not performed.
