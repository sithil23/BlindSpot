# BLINDSPOT behavior contract

Product rules: `SPEC.md`; measurement settings: `blindspot/models.py`.
Privacy: local process; participant codes only; summaries stored only by explicit Save session;
raw frames never stored. No external transmission by the app. No auto-save or deletion UI.
History controls remain in session state because participant data should not appear in URLs.
Locale: English. Saved time displayed in Asia/Colombo with timezone text; UTC epoch in receipts.

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Form | Streamlit labelled inputs + app validation | SPEC.md | assessment settings | tests/test_ui.py |
| Scrollbar | blindspot/assets/theme.css | DESIGN.md | global baseline | tests/browser_check.py |
| Toast | Streamlit persistent status/alert | UX-CONTRACT.md | success/info/warning/error | tests/test_ui.py |
| CRUD | SessionStore + shared result renderer | SPEC.md | explicit idempotent save/read | tests/test_sessions.py |

Single-select and date controls are absent. Tabs and radios are framework-owned. No custom popup.
Assessment: settings -> start -> setup spinner -> elapsed capture -> result -> optional Save session.
Changing settings cannot relabel an already completed result. Camera error retains last result.
Lab: choose fault -> run deterministic assessment -> shared result -> optional Save session.
Lab comparison history consists of three explicitly synthetic fixtures, never stored as webcam data.
Save: same UUID -> pending transaction -> persistent saved state; failure retains result and offers retry.
History: empty guidance or 10 rows -> previous/next -> saved receipt downloads. No unbounded table.
Receipt includes protocol settings, observed count, evidence reasons, baseline IDs, provenance and limits.
No performance conclusion when evidence fails. Valid session without sufficient baseline requests more data.
