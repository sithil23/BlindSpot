# BLINDSPOT prototype scope

Remake the uploaded HMS prototype as a local Python performance-measurement tool.
The source archive is preserved outside this working project. Its SQLite logging pattern
is adapted with explicit sessions, errors, transactions and provenance; no HMS risk model
or medical thresholds are carried into this application.

## Acceptance criteria
- A completed thumb/index open-close-open cycle counts once with hysteresis and debounce.
- Loss of tracking, sequence replay, malformed data, inadequate coverage, long gaps and
  stream expiry are independently visible. Quality is audited at session end, even with no input.
- No cycle bridges tracking loss. Repeated distances alone do not imply failure.
- Three prior eligible sessions of the same participant, hand, protocol and source are
  needed for a descriptive comparison. Synthetic sessions never enter webcam baselines.
- Bad sessions never enter baselines. Missing rates remain null. No clinical interpretation.
- Fault lab applies deterministic loss, stale-stream, low-confidence and sequence replay
  faults to the same 30-cycle synthetic motion, showing basic versus evidence-aware conclusions.
- Local OpenCV + MediaPipe Tasks webcam capture never stores raw images or video.
- Camera/dependency/model failures offer a clear recovery path and retain the offline demo.
- Streamlit assessment, lab, history and research views share clear states and labels.
- A packaged NASA research adapter supplies sourced context to the UI and evidence receipts,
  without suggesting NASA validation or NASA-derived patient data.

## Boundaries
Single user, local process and SQLite. No cloud hosting, API, telemetry, clinical scoring,
accounts, model training, or diagnostic claims. Webcam is on the machine running Python;
a remote Streamlit server cannot access the viewer's camera. Set up the hand model once
before offline use. Quality policy values are engineering demo settings, not validated limits.
