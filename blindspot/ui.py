

import json
import os
import re
import sqlite3
from dataclasses import asdict
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from blindspot.assessment import assess
from blindspot.camera import DEFAULT_MODEL, CameraUnavailable, capture
from blindspot.evidence import REASONS
from blindspot.lab import run_lab
from blindspot.models import Observation, Protocol, usable
from blindspot.preview_rate import should_update
from blindspot.nasa import research_context
from blindspot.sessions import Session, compare
from blindspot.storage import SessionStore
from blindspot.synthetic import SCENARIOS
from blindspot.tapping import TapCounter
from blindspot.telemetry import CHANNELS, SCENARIOS as MISSION_SCENARIOS, generate_mission, summarize, telemetry_receipt
from blindspot.navigation import eva_progress, homepage_summary
from blindspot.remote_api import fetch_remote, fetch_post_eva, fetch_crew_remote, fetch_radiation_remote, RemoteTelemetryError
from blindspot.dashboard import dashboard_flags, crew_summary
from blindspot.meals import CREW_IDS, MealStore, meal_status, meal_summary
from blindspot.crew_attention import rank_crew, priority_alert, crew_report
from blindspot.voice_alerts import voice_widget_html
from blindspot.demo_controls import SCENARIOS as DEMO_SCENARIOS, apply_demo, gravity_reading, trend_history
from blindspot.plain_charts import line_chart_svg
from blindspot.radiation import apply_radiation_demo, radiation_flags
from html import escape


def stylesheet() -> str:
    return files("blindspot").joinpath("assets/theme.css").read_text(encoding="utf-8")


def trace_svg(frames: list[Observation], policy: Protocol) -> str:
    """A gap-preserving trace with text alternatives; no user text enters the markup."""
    tokens = dict(re.findall(r"--bs-([\w-]+):\s*(#[0-9a-f]+)", stylesheet()))
    expected = round(policy.duration_s * policy.fps)
    valid_bins = set()
    paths: list[list[str]] = []
    segment: list[str] = []
    last_seq = -1
    last_t = -1.0
    for frame in frames:
        valid = usable(frame, policy) and frame.seq > last_seq and frame.t > last_t
        if valid and last_t >= 0 and frame.t - last_t > policy.bridge_gap_s:
            if segment:
                paths.append(segment)
            segment = []
        if valid:
            valid_bins.add(int(frame.t * policy.fps + 1e-7))
            x = 30 + frame.t / policy.duration_s * 840
            y = 140 - min(frame.distance or 0, 1.2) / 1.2 * 90
            segment.append(f"{x:.1f},{y:.1f}")
        elif segment:
            paths.append(segment)
            segment = []
        last_seq = max(last_seq, frame.seq)
        last_t = max(last_t, frame.t)
    if segment:
        paths.append(segment)
    lines = "".join(
        f'<polyline points="{" ".join(p)}" fill="none" '
        f'stroke="{tokens["primary"]}" stroke-width="2" />'
        for p in paths
    )
    strip = "".join(
        f'<rect x="{30 + i / expected * 840:.2f}" y="30" '
        f'width="{840 / expected + 0.1:.2f}" height="20" '
        f'fill="{tokens["success"] if i in valid_bins else tokens["warning"]}" />'
        for i in range(expected)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 178" role="img" '
        'aria-labelledby="trace-title trace-description">'
        '<title id="trace-title">Hand movement and usable tracking over time</title>'
        f"<style>text {{ font-family: monospace; fill: {tokens['muted']}; "
        "font-size: 12px; }</style>"
        '<desc id="trace-description">Upper band shows usable tracking in teal and missing '
        "or rejected frames in amber. Blue curve shows normalized finger separation. "
        "Gaps are preserved. Coverage and longest gap are also reported as text below.</desc>"
        f'<text x="30" y="18">TRACKING AVAILABILITY</text>{strip}{lines}'
        '<text x="30" y="168">0 s</text>'
        f'<text x="825" y="168">{policy.duration_s:g} s</text></svg>'
    )


def render_result(bundle, policy: Protocol, store: SessionStore):
    session, frames, comparison, receipt, basic = bundle
    result = session.assessment
    st.html(f'<div class="plain-svg-chart">{trace_svg(frames, policy)}</div>')
    metrics = st.columns(4)
    metrics[0].metric("Observed cycles", str(result.count) if result.rate_hz is not None else "—")
    metrics[1].metric("Usable tracking", f"{result.evidence.coverage:.0%}")
    metrics[2].metric("Longest tracking gap", f"{result.evidence.longest_gap_s:.2f} s")
    metrics[3].metric("Elapsed assessment", f"{result.duration_s:.1f} s")
    if session.source == "webcam":
        actual_fps = session.metadata.get("effective_fps")
        if isinstance(actual_fps, (int, float)):
            if actual_fps < 10:
                st.warning(
                    "Camera processing is slow. Rapid finger taps may occur between "
                    "processed frames and be missed. Close other applications, improve "
                    "lighting, and try again; do not treat this count as a reliable "
                    "performance measurement."
                )
    if session.source == "webcam":
        distances = [f.distance for f in frames if usable(f, policy)]
        if distances:
            close_samples = sum(d <= policy.close_ratio for d in distances)
            open_samples = sum(d >= policy.open_ratio for d in distances)
    if comparison.status == "insufficient_evidence":
        st.warning(comparison.explanation)
        for reason in result.evidence.reasons:
            st.write("• " + REASONS[reason])
    elif comparison.status == "baseline_needed":
        st.info(comparison.explanation)
    else:
        st.success(comparison.explanation)
    if basic:
        with st.container(border=True):
            st.markdown("**What a basic monitor would show**")
            st.write(basic)
    if not result.evidence.sufficient:
        pass
    left, right = st.columns(2)
    public = os.environ.get("BLINDSPOT_PUBLIC", "0") == "1"
    saved = public or store.get(session.id) is not None
    if left.button(
        "Saving disabled on public demo" if public else "Session saved" if saved else "Save session",
        disabled=saved,
        key=f"save-{session.id}",
        width="stretch",
    ):
        try:
            store.save(session, receipt)
            st.success(
                "Session saved. The summary and evidence receipt are available in Session log."
            )
        except (sqlite3.Error, OSError):
            st.error(
                "Session could not be saved. Check the database folder permissions and retry. "
                "You can still download the receipt."
            )
    right.download_button(
        "Download evidence receipt",
        json.dumps(receipt, indent=2, allow_nan=False),
        file_name=f"blindspot-{session.id[:8]}.json",
        mime="application/json",
        key=f"download-{session.id}",
        width="stretch",
    )
    with st.expander("Inspect the evidence receipt"):
        st.json(receipt, expanded=False)


def assessment_view(store: SessionStore):
    if os.environ.get("BLINDSPOT_PUBLIC", "0") == "1":
        st.info("Live webcam processing is available in the local desktop installation only. The public server cannot access your device camera. Use Mission overview or Scenario lab for the online demo.")
        return
    st.subheader("Measure a tapping session")
    st.write(
        "Touch your index finger to your thumb, then open them fully. "
        "Each open–close–open movement is one cycle. Keep one hand fully in view."
    )
    a, b, c = st.columns([2, 1, 1])
    participant = a.text_input(
        "Participant code",
        value="P01",
        max_chars=64,
    )
    hand = b.radio("Hand to assess", ["Right", "Left"], horizontal=True)
    camera_index = c.number_input("Camera index", min_value=0, max_value=9, value=0, step=1)
    with st.expander("Camera speed and tap sensitivity", expanded=False):
        show_preview = st.checkbox(
            "Show live preview (slower)", value=False,
        )
        close_ratio = st.slider(
            "Fingers together threshold", 0.20, 0.50, 0.34, 0.01,
        )
        open_ratio = st.slider(
            "Fingers apart threshold", 0.51, 0.90, 0.56, 0.01,
        )
    policy = Protocol(hand=hand, close_ratio=close_ratio, open_ratio=open_ratio)
    if not DEFAULT_MODEL.exists():
        st.info(
            "Camera setup needed: install the camera extras and run "
            "`python -m blindspot prepare-camera` once. The Fault lab works without a camera."
        )
    start = st.button("Start 15-second assessment", type="primary")
    progress = st.empty()
    preview = st.empty()
    if start:
        if not participant.strip():
            st.error("Enter a participant code before starting.")
        else:
            try:

                live_counter = TapCounter(policy)
                last_preview = -1.0
                last_progress = -1.0

                def on_frame(t, frame, rgb):
                    nonlocal last_preview, last_progress
                    live_counter.update(frame)
                    # Streamlit rendering is synchronous and can starve camera processing.

                    if should_update(t, last_progress, 0.75):
                        progress.progress(
                            min(1.0, t / policy.duration_s),
                            text=f"{t:.1f} / 15 s · {live_counter.count} observed cycles · "
                            f"{'hand visible' if usable(frame, policy) else 'tracking unavailable'}",
                        )
                        last_progress = t
                    if show_preview and rgb is not None and should_update(t, last_preview, 1.0):
                        preview.image(
                            rgb, width=480
                        )
                        last_preview = t

                with st.spinner("Opening local camera. Hold your hand ready."):
                    captured = capture(policy, camera_index=int(camera_index), progress=on_frame)
                session = Session.create(
                    participant,
                    "webcam",
                    policy,
                    assess(captured.frames, policy, captured.duration_s),
                    metadata=captured.metadata,
                )
                comparison = compare(session, store.baseline_candidates(session, policy), policy)
                st.session_state.camera_result = (
                    session,
                    captured.frames,
                    comparison,
                    session.receipt(comparison, policy),
                    None,
                )
                st.session_state.camera_policy = policy
            except CameraUnavailable as exc:
                st.error(str(exc))
            finally:
                progress.empty()
                preview.empty()
    if "camera_result" in st.session_state:
        render_result(st.session_state.camera_result, st.session_state.camera_policy, store)
    else:
        st.info(
            "No assessment yet. Start a local camera session, "
            "or open Fault lab for a repeatable demo."
        )


def lab_view(store: SessionStore):
    st.subheader("Break the measurement, keep the motion")
    st.write(
        "The same synthetic hand completes 30 cycles in 15 seconds. "
        "Change only the tracking evidence and compare the interpretations."
    )
    scenario = st.radio(
        "Inject a measurement fault",
        list(SCENARIOS),
        index=1,
        format_func=SCENARIOS.get,
        horizontal=True,
    )
    if st.button("Run fault demonstration", type="primary"):
        st.session_state.lab_result = run_lab(scenario)
    if "lab_result" in st.session_state:
        render_result(st.session_state.lab_result, Protocol(), store)
    else:
        st.info("Choose a fault and run the demonstration. No camera or internet is needed.")


def history_view(store: SessionStore):
    st.subheader("Session log")
    total = store.count()
    if not total:
        st.info(
            "No saved sessions. Run an assessment or fault demonstration, then choose Save session."
        )
        return
    page = min(st.session_state.get("history_page", 0), (total - 1) // 10)
    rows = store.recent(limit=10, offset=page * 10)
    st.write(f"Showing {page * 10 + 1}–{min((page + 1) * 10, total)} of {total} sessions")
    for session in rows:
        stamp = datetime.fromtimestamp(session.created_at, ZoneInfo("Asia/Colombo")).strftime(
            "%d %b %Y %H:%M"
        )
        quality = (
            "Usable evidence" if session.assessment.evidence.sufficient else "Insufficient evidence"
        )
        label = f"{stamp} · {session.participant} · {session.source} · {quality}"
        with st.expander(label):
            st.write(
                f"Observed cycles: {session.assessment.count} · "
                f"Usable tracking: {session.assessment.evidence.coverage:.0%}"
            )
            receipt = store.receipt(session.id)
            if receipt:
                st.write(receipt["comparison"]["explanation"])
                st.download_button(
                    "Download saved receipt",
                    json.dumps(receipt, indent=2),
                    file_name=f"blindspot-{session.id[:8]}.json",
                    mime="application/json",
                    key=f"history-{session.id}",
                )
            else:
                pass
    previous, next_page, _ = st.columns([1, 1, 3])
    if previous.button("Previous page", disabled=page == 0):
        st.session_state.history_page = page - 1
        st.rerun()
    if next_page.button("Next page", disabled=(page + 1) * 10 >= total):
        st.session_state.history_page = page + 1
        st.rerun()


def research_view():
    st.subheader("Research context and boundaries")
    source = research_context()
    st.markdown(f"**[{source['title']}]({source['url']})**")
    st.write(source["summary"])
    st.write(source["application"])
    st.info(source["limitations"])
    st.markdown("**What the prototype can establish**")
    st.write(
        "A count of observed hand movements, measured tracking availability, "
        "and a descriptive comparison with eligible prior sessions."
    )
    st.markdown("**What it cannot establish**")
    st.write(
        "A diagnosis, fatigue level, cause of a change, readiness for duty, or reliability "
        "under spaceflight conditions. Occlusion, camera angle, lighting and hand "
        "classification can affect results. Persistent wrong landmarks can pass the audit."
    )
    with st.expander("Measurement policy and baseline rules"):
        st.json(asdict(Protocol()))
        st.write(
            "Use the same hand, camera placement and movement instructions. "
            "The baseline uses the most recent 20 eligible prior sessions within 30 days, "
            "with at least three required. Synthetic and webcam baselines are separated. "
            "Equal measured values alone never imply sensor failure."
        )


def remote_mission_view():

    st.subheader('Remote synthetic sensor feed')
    url = os.environ.get('BLINDSPOT_SENSOR_API_URL', '').strip()
    token = os.environ.get('BLINDSPOT_SENSOR_TOKEN', '').strip()
    if not url or not token:
        st.warning('Remote feed is not configured. Set BLINDSPOT_SENSOR_API_URL and BLINDSPOT_SENSOR_TOKEN on the Streamlit host.')
        return
    st.button('Refresh sensor readings', key='remote-refresh', type='primary')
    try:
        data = fetch_remote(url, token, allow_http_local=True)
    except RemoteTelemetryError as exc:
        st.error(f'Remote data unavailable or rejected: {exc}')
        return
    channels = data['channels']
    severity, message = homepage_summary(channels, data['scenario'])
    if severity == 'warning':
        st.warning(message)
    elif severity == 'info':
        st.info(message)
    else:
        st.success(message)
    selected = ('heart_rate', 'spo2', 'cabin_co2', 'cabin_o2')
    cells = st.columns(2)
    for i, key in enumerate(selected):
        item = channels[key]
        with cells[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{item['label']}**")
                if item['quality'] == 'adequate':
                    st.metric('Reading', f"{item['value']:g} {item['unit']}", label_visibility='collapsed')
                else:
                    st.metric('Reading', 'Unavailable', label_visibility='collapsed')
                    st.warning('Insufficient evidence — verify simulated channel')
    with st.expander('All remote channels and evidence'):
        for item in channels.values():
            value = f"{item['value']:g} {item['unit']}" if item['value'] is not None else 'No reliable reading'
            st.write(f"**{item['label']}**: {value} · {item['quality']}")
        st.download_button('Download remote evidence (JSON)', json.dumps(data, indent=2),
                           file_name='blindspot-remote-synthetic.json', mime='application/json',
                           key='remote-evidence')


def _clear_demo():

    st.session_state['demo_event'] = 'routine'


def meal_panel(store, records):
    st.markdown('### Crew nutrition')
    if store is None:
        st.error('Meal records unavailable. Check the database path and write permissions.')
        return

    cols = st.columns(3, gap='small')
    now = datetime.now(ZoneInfo('UTC'))
    for col, crew_id in zip(cols, CREW_IDS):
        record = records.get(crew_id)
        state = meal_status(record['eaten_at'] if record else None, now)
        warning = state['state'] == 'reminder'
        label = 'No meal recorded' if not record else datetime.fromisoformat(record['eaten_at']).strftime('%d %b %H:%M UTC')
        next_label = state['next_meal'].strftime('%d %b %H:%M UTC') if state['next_meal'] else 'Not available'
        note = ('MEAL REMINDER · Member, you should eat now. Confirm with crew.' if warning
                else 'Suggested meal time passed; no new meal logged.' if state['state'] == 'overdue'
                else 'Meal time awaiting confirmation.' if state['state'] == 'no_record'
                else 'Meal timestamp needs review.' if state['state'] == 'invalid'
                else 'Upcoming suggested meal')
        if record and record.get('needs_review'):
            note += ' · Auto-scanned; actual intake and portion not confirmed.'
        style = ' meal-card-overdue' if warning else ''
        with col:
            st.markdown(
                f'<div class="meal-card{style}"><strong>{escape(crew_id)}</strong>'
                f'<div>Last meal: {escape(label)}</div>'
                f'<div>Next suggested: {escape(next_label)}</div>'
                f'<div class="meal-card-note">{escape(note)}</div></div>', unsafe_allow_html=True)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            totals = meal_summary(store.meal_history(crew_id, since=start))
            st.write(f'Logged today: {totals["energy_kcal"]:.0f} kcal · {totals["protein_g"]:.1f} g protein')



def food_management_view():
    from blindspot.barcode_camera import scan_barcode
    from blindspot.food_lookup import lookup_food, normalize_barcode
    from blindspot.face_profiles import enroll, enrolled_counts, recognize, delete_profile

    st.subheader('Food Management')
    try:
        store = MealStore()
    except (OSError, sqlite3.Error) as exc:
        st.error(f'Food database not available: {exc}')
        return

    if st.button('Register crew member', key='food-register-toggle'):
        st.session_state['food-registration-open'] = not st.session_state.get('food-registration-open', False)

    if st.session_state.get('food-registration-open', False):
        st.markdown('#### Crew registration')
        enrollment_crew = st.selectbox('Crew member', CREW_IDS, key='enroll-crew')
        try:
            counts = enrolled_counts()
        except (OSError, ValueError, ImportError) as exc:
            counts = {}
            st.warning(str(exc))
        already = counts.get(enrollment_crew, 0)
        st.write(f'{enrollment_crew} · {min(already, 3)}/3 photos')
        consent = st.checkbox('I have permission to register this crew member', key='food-face-consent')
        if already < 3:
            capture = st.camera_input('Registration photo', key=f'enroll-face-{enrollment_crew}-{st.session_state.get("face-enroll-n", 0)}')
            if st.button('Save registration photo', disabled=not consent or capture is None):
                try:
                    count = enroll(enrollment_crew, capture.getvalue())
                    st.session_state['face-enroll-n'] = st.session_state.get('face-enroll-n', 0) + 1
                    st.rerun()
                except (ValueError, RuntimeError, OSError) as exc:
                    st.error(str(exc))
        else:
            st.success('Registration complete')
        if st.button('Delete registration'):
            try:
                delete_profile(enrollment_crew)
                st.rerun()
            except (ValueError, RuntimeError, OSError) as exc:
                st.error(str(exc))

    st.markdown('#### Record meal')
    left, right = st.columns(2, gap='large')
    with left:
        photo = st.camera_input('Meal camera', key=f'food-shared-camera-{st.session_state.get("food-camera-n", 0)}')
        action_left, action_right = st.columns(2)
        if action_left.button('Recognize member', disabled=photo is None):
            try:
                candidate = recognize(photo.getvalue())
                if candidate:
                    st.session_state['food-crew-id'] = candidate
                    st.success(f'Member: {candidate}')
                else:
                    st.warning('No confident match. Select member manually.')
            except (RuntimeError, ValueError, OSError) as exc:
                st.warning(str(exc))
        if action_right.button('Read barcode number', disabled=photo is None):
            try:
                code = scan_barcode(photo.getvalue())
                if code:
                    st.session_state['food-manual-code'] = code
                    st.success(f'Barcode: {code}')
                    st.session_state['food-camera-n'] = st.session_state.get('food-camera-n', 0) + 1
                else:
                    st.warning('Barcode number not found. Try another photo.')
            except (RuntimeError, ValueError) as exc:
                st.warning(str(exc))
        selected_crew = st.selectbox('Member', CREW_IDS, key='food-crew-id')
        manual_code = st.text_input('Barcode number', key='food-manual-code')
        if st.button('Find product online', type='primary'):
            try:
                code = normalize_barcode(manual_code)
                st.session_state.pop('food-found-product', None)
                cached = store.find_food(code)
                if cached:
                    st.session_state['food-found-product'] = {'barcode': code, 'label':cached['label'],
                        'energy_kcal':cached['energy_kcal'],'protein_g':cached['protein_g'],
                        'carbs_g':cached['carbs_g'],'fat_g':cached['fat_g'], 'serving_basis':('100 g / 100 ml' if cached['basis'] == '100g' else 'catalog serving'), 'source':'local catalog'}
                else:
                    found = lookup_food(code)
                    if found is None:
                        st.warning('Product not found or nutrition data incomplete. Enter verified label data below.')
                    else:
                        st.session_state['food-found-product'] = {**found, 'source':'Open Food Facts'}
                        st.success('Food found. Verify the label and portion before saving.')
            except (ValueError, LookupError) as exc:
                st.warning(str(exc))

    with right:
        st.markdown('#### Meal details')
        product = st.session_state.get('food-found-product')
        if product and manual_code.strip() != product['barcode']:
            product = None
        if product:
            st.markdown(f'**{escape(product["label"])}**')
            st.write(f'{product["source"]} · per {product["serving_basis"]}')
            for name, unit in [('energy_kcal','kcal'), ('protein_g','g protein'), ('carbs_g','g carbohydrates'),('fat_g','g fat')]:
                st.write(f'{product[name]:g} {unit}')
            if product['serving_basis'] == '100 g / 100 ml':
                grams = st.number_input('Amount eaten (g / ml, as labeled)', min_value=1.0, max_value=2000.0,
                                        value=100.0, step=25.0, key='food-consumed-grams')
                servings = grams / 100.0

            else:
                servings = st.number_input('Servings eaten', min_value=0.25,max_value=20.0,
                                           value=1.0,step=0.25,key='food-consumed-servings')
            if st.button('Save meal', type='primary'):
                try:
                    if product['source'] == 'Open Food Facts':
                        store.save_food(product['barcode'], product['label'], product['energy_kcal'],
                            product['protein_g'], product['carbs_g'], product['fat_g'], basis='100g')
                    store.record_meal(selected_crew, product['barcode'], servings)
                    st.session_state.pop('food-found-product', None)
                    st.success(f'Meal saved for {selected_crew}. Crew nutrition will update on Mission Overview.')
                except (ValueError, sqlite3.Error, OSError) as exc:
                    st.error(str(exc))

        with st.expander('Add an unlisted barcode manually'):
            with st.form('food-catalog-form', clear_on_submit=True):
                new_code = st.text_input('Food barcode',key='food-new-barcode')
                food_label = st.text_input('Food name',key='food-label')

                kcal = st.number_input('Energy (kcal)', min_value=0., value=0.,key='food-kcal')
                protein = st.number_input('Protein (g)', min_value=0., value=0.,key='food-protein')
                carbs = st.number_input('Carbs (g)', min_value=0., value=0.,key='food-carbs')
                fat = st.number_input('Fat (g)', min_value=0., value=0.,key='food-fat')
                if st.form_submit_button('Add to local food catalog'):
                    try:
                        store.save_food(new_code,food_label,kcal,protein,carbs,fat)
                        st.success('Food saved to the local catalog. Look up its barcode to record a meal.')
                    except (ValueError, sqlite3.Error, OSError) as exc:
                        st.error(str(exc))



@st.fragment(run_every="5s")
def multi_crew_live_dashboard():
    """Auto-refresh only this fragment, not the spacewalk check or camera workflow."""
    first_url = os.environ.get('BLINDSPOT_SENSOR_API_URL', '').strip()
    second_url = os.environ.get('BLINDSPOT_SENSOR_API_URL_2', '').strip()
    token1 = os.environ.get('BLINDSPOT_SENSOR_TOKEN', '').strip()
    token2 = os.environ.get('BLINDSPOT_SENSOR_TOKEN_2', token1).strip()
    # The first two astronauts come from sensor simulator A; the third comes from B.
    sources = [('CREW-01', first_url, token1, 'Feed A'),
               ('CREW-02', first_url, token1, 'Feed A'),
               ('CREW-03', second_url, token2, 'Feed B')]
    crew = {}
    errors = {}
    for crew_id, url, token, label in sources:
        try:
            if not url or not token:
                raise RemoteTelemetryError(f'{label} is not configured')
            crew[crew_id] = fetch_crew_remote(url, token, crew_id, allow_http_local=True)
        except RemoteTelemetryError as exc:
            crew[crew_id] = None
            errors[crew_id] = str(exc)

    habitat = {}
    for name, url, token in [('Habitat A', first_url, token1), ('Habitat B', second_url, token2)]:
        try:
            if not url or not token:
                raise RemoteTelemetryError('not configured')
            habitat[name] = fetch_remote(url, token, allow_http_local=True)
        except RemoteTelemetryError:
            habitat[name] = None

    scenario = st.session_state.get('demo_event', 'routine')
    target = st.session_state.get('demo_crew', 'CREW-01')
    displayed, demo_flags = apply_demo(crew, habitat, scenario, target)
    shown_crew = {name: displayed.get(name) for name in crew}
    shown_habitat = {name: displayed.get(name) for name in habitat}

    radiation_feeds = {}
    for name, url, token in [('A', first_url, token1), ('B', second_url, token2)]:
        try:
            if not url or not token:
                raise RemoteTelemetryError('Radiation feed not configured')
            radiation_feeds[name] = fetch_radiation_remote(url, token, allow_http_local=True)
        except RemoteTelemetryError:
            radiation_feeds[name] = None

    radiation_rows = {'crews': {}, 'habitats': {}}
    for crew_id in shown_crew:
        feed = radiation_feeds['B' if crew_id == 'CREW-03' else 'A']
        radiation_rows['crews'][crew_id] = (feed or {}).get('crews', {}).get(crew_id)
    for habitat_id in shown_habitat:
        feed = radiation_feeds['B' if habitat_id == 'Habitat B' else 'A']
        radiation_rows['habitats'][habitat_id] = (feed or {}).get('habitats', {}).get(habitat_id)

    flags = demo_flags + dashboard_flags(shown_crew, shown_habitat)
    if scenario in ('radiation_event', 'radiation_sensor_loss'):
        feed_name = 'B' if target == 'CREW-03' else 'A'
        selected_feed, injected_flags = apply_radiation_demo(radiation_feeds[feed_name], scenario, target)
        if selected_feed is not None:
            radiation_rows['crews'][target] = selected_feed['crews'][target]
        flags.extend(injected_flags)
    for name, row in {**radiation_rows['crews'], **radiation_rows['habitats']}.items():
        if row is None or row['quality'] != 'adequate':
            flags.append({'kind': 'evidence', 'message': f'{name} radiation feed unavailable. Exposure cannot be assessed.'})


    try:
        meal_db = MealStore()
        meal_records = {crew_id: meal_db.latest_meal(crew_id) for crew_id in CREW_IDS}
        for crew_id, record in meal_records.items():
            if record and meal_status(record['eaten_at'])['state'] == 'reminder':
                flags.append({'kind': 'warning',
                              'message': f'{crew_id}: meal reminder — member, you should eat now. No meal logged since the suggested time; confirm with the crew.'})
    except (OSError, sqlite3.Error, ValueError):
        meal_db = None
        meal_records = {}

    if any(flag["kind"] in ("critical", "warning", "feed", "evidence") for flag in flags):
        st.markdown(
            '<style class="dashboard-alert-shade">'
            '.stApp {'
            'background-image:'
            'radial-gradient(ellipse at 0% 55%, rgba(195, 38, 51, .07), transparent 38%),'
            'radial-gradient(ellipse at 100% 55%, rgba(195, 38, 51, .07), transparent 38%),'
            'radial-gradient(ellipse at 50% 47%, rgba(195, 38, 51, .045), transparent 44%);'
            '}'
            '</style>',
            unsafe_allow_html=True,
        )
    warning_left, warning_right = st.columns([3, 7], gap="medium")
    with warning_left:
        st.markdown('<div class="dashboard-section-label">Mission status</div>', unsafe_allow_html=True)
        status_label = f'{len(flags)} active flag(s)' if flags else 'All feeds reporting'
        st.markdown(f'<div class="dashboard-status-box"><strong>{escape(status_label)}</strong></div>', unsafe_allow_html=True)
        import streamlit.components.v1 as components
        components.html(voice_widget_html(flags), height=46, scrolling=False)
    with warning_right:
        ordered = sorted(flags, key=lambda f: {'critical': 0, 'warning': 1, 'feed': 2, 'evidence': 3, 'trend': 4, 'context': 5}.get(f['kind'], 6))
        bits = ['<div class="dashboard-warning-shell"><div class="dashboard-section-label">Alerts</div>']
        if not ordered:
            bits.append('<div class="dashboard-warning-entry" role="status"><strong>Status</strong><div>No active warnings</div></div>')
        else:
            for flag in ordered[:8]:
                kind = flag['kind']
                heading = 'CRITICAL · MONITORING OUTAGE' if kind == 'critical' else 'WARNING' if kind in ('warning', 'feed', 'evidence') else 'NOTICE'
                border = '#ae2828' if kind == 'critical' else '#a85a00' if kind in ('warning', 'feed', 'evidence') else '#24599b'
                bits.append(f'<div class="dashboard-warning-entry" role="alert" style="border-left:5px solid {border}"><strong>{heading}</strong><div>{escape(flag["message"])}</div></div>')
            if len(ordered) > 8:
                bits.append(f'<div class="dashboard-warning-more">{len(ordered) - 8} more flags</div>')
        bits.append('</div>')
        st.markdown(''.join(bits), unsafe_allow_html=True)


    attention = rank_crew(shown_crew, flags)
    st.markdown('### Crew follow-up')
    attention_columns = st.columns(3, gap="small")
    reports = []
    for position, (column, item) in enumerate(zip(attention_columns, attention), start=1):
        stats = item['stats']
        notice = priority_alert(item)
        details = [('Medical', item['medical']), ('Rest', item['rest']),
                   ('Exercise', item['exercise']), ('Sleep', item['sleep'])]

        def reading(key, unit):
            value = stats[key]
            return f'{value:g} {unit}' if value is not None else 'No data'

        rows = ''.join(f'<div><b>{escape(label)}</b>: {escape(value)}</div>' for label, value in details)
        warning_class = ' crew-attention-flagged' if notice['highlight'] else ''
        action = (
            '<div class="crew-attention-review" role="status">'
            'CRITICAL REPORT · Crew review requested'
            '<div>Report ready for other crew members. Not transmitted.</div>'
            '</div>'
        ) if notice['highlight'] else ''
        with column:
            st.markdown(
                f'<div class="crew-attention-item{warning_class}">'
                f'<strong>#{position} {escape(item["crew_id"])}</strong>'
                f'<div class="crew-attention-state">{escape(item["state"])}</div>'
                f'<div>HR: {escape(reading("heart_rate", "bpm"))} · '
                f'SpO₂: {escape(reading("spo2", "%"))}</div>'
                f'<div>Breathing: {escape(reading("respiration", "/min"))} · '
                f'Temperature: {escape(reading("body_temp", "°C"))}</div>'
                f'{rows}{action}</div>', unsafe_allow_html=True,
            )
        if notice['highlight']:
            reports.append(crew_report(item))
    if reports:
        st.download_button('Download crew review report',
                           json.dumps(reports, indent=2),
                           file_name='blindspot-crew-review.json',
                           mime='application/json', key='crew-review-report')
    st.markdown('<p class="crew-attention-note">Monitoring follow-up only; no medical diagnosis or automatic report delivery.</p>', unsafe_allow_html=True)

    meal_panel(meal_db, meal_records)

    st.markdown('### Crew')
    columns = st.columns(3)
    specs = [('heart_rate', 'Heart rate', 'bpm'), ('spo2', 'Blood oxygen', '%'),
             ('respiration', 'Breathing', 'breaths/min'), ('body_temp', 'Temperature', '°C')]
    for col, (crew_id, _, _, source) in zip(columns, sources):
        with col:
            with st.container(border=True):
                st.markdown(f'**{crew_id}** · {source}')
                record = shown_crew[crew_id]
                if record is None:
                    st.error('NO SENSOR DATA')
                else:
                    readings = crew_summary(record)
                    for key, label, unit in specs:
                        value = readings[key]
                        st.metric(label, f'{value:g} {unit}' if value is not None else 'No data')

    st.markdown('### Habitats')
    cols = st.columns(2)
    for col, name in zip(cols, ('Habitat A', 'Habitat B')):
        with col:
            with st.container(border=True):
                st.markdown(f'**{name}**')
                record = shown_habitat[name]
                if record is None:
                    st.error('NO SENSOR DATA')
                else:
                    for key, label in [('cabin_o2', 'Oxygen'), ('cabin_co2', 'CO₂'),
                                       ('cabin_pressure', 'Pressure')]:
                        item = record['channels'][key]
                        st.metric(label, f'{item["value"]:g} {item["unit"]}' if item['quality'] == 'adequate' else 'No data')

    st.markdown('### Radiation')
    st.markdown('<div class="dashboard-section-label">Synthetic personal and habitat dosimeters · Dose equivalent</div>', unsafe_allow_html=True)
    with st.expander('Research sources'):
        st.markdown('[CSA: Neutron monitoring](https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp) · [NASA RadLab](https://visualization.osdr.nasa.gov/radlab)')
        st.write('This demo generates its own dose-equivalent values; it does not stream CANS or NASA RadLab data. Alarm scenarios are not flight safety thresholds.')
    radiation_cols = st.columns(3, gap='small')
    for col, (name, item) in zip(radiation_cols, radiation_rows['crews'].items()):
        with col:
            with st.container(border=True):
                st.markdown(f'**{name}**')
                if item is None or item['quality'] != 'adequate':
                    st.metric('Dose rate', 'No data')
                    st.metric('Accumulated', 'Unknown')
                else:
                    st.metric('Dose rate', f'{item["dose_equivalent_rate_uSv_h"]:.2f} µSv/h')
                    st.metric('Accumulated', f'{item["cumulative_dose_uSv"]:.3f} µSv')
    radiation_cols = st.columns(2, gap='small')
    for col, (name, item) in zip(radiation_cols, radiation_rows['habitats'].items()):
        with col:
            with st.container(border=True):
                label = 'No data' if item is None or item['quality'] != 'adequate' else f'{item["dose_equivalent_rate_uSv_h"]:.2f} µSv/h'
                st.metric(f'{name} dose rate', label)

    # Keep bounded browser-session charts; never persist injected demo measurements to the API or SQLite.
    # Each graph is built only from the feed it names, with missing values as gaps.
    hist = st.session_state.setdefault('dashboard_charts_v11', {})
    chart_sources = {}
    for entity, payload in {**shown_crew, **shown_habitat}.items():
        if entity.startswith('CREW-'):
            fields = ('heart_rate', 'spo2', 'respiration')
        else:
            fields = ('cabin_o2', 'cabin_co2', 'cabin_pressure')
        for channel in fields:
            key = f'{entity}/{channel}'
            current = payload['channels'][channel] if payload is not None else None
            good = current is not None and current['quality'] == 'adequate'
            value = current['value'] if good else None
            previous = hist.get(key, [])
            sequence = payload['sequence'] if payload is not None else ((previous[-1]['sequence'] + 1) if previous else 0)
            # Sequence may wrap at the simulator's 120-second cycle; record the restarted sequence.
            if previous and sequence < previous[-1]['sequence']:
                previous = []
            hist[key] = trend_history(previous, entity, channel, value, sequence, 60)
            chart_sources[key] = hist[key]
    st.markdown('### Sensor trends')
    filter_left, filter_right = st.columns(2)
    with filter_left:
        selected_crew = st.selectbox('Astronaut', list(shown_crew), key='trend_crew')
    with filter_right:
        selected_habitat = st.selectbox('Habitat', list(shown_habitat), key='trend_habitat')



    tick = max((p['sequence'] for p in [*shown_crew.values(), *shown_habitat.values()] if p is not None), default=0)
    g_history = st.session_state.setdefault('simulated_acceleration_v11', [])
    if g_history and tick < g_history[-1]['sequence']:
        g_history = []
    g_history = trend_history(g_history, 'simulation', 'acceleration', gravity_reading(scenario, tick), tick, 60)
    st.session_state['simulated_acceleration_v11'] = g_history

    chart_specs = [
        (selected_crew, 'heart_rate', 'Heart rate', 'bpm'),
        (selected_crew, 'spo2', 'Blood oxygen', '%'),
        (selected_crew, 'respiration', 'Breathing', 'breaths/min'),
        (selected_habitat, 'cabin_co2', 'Cabin CO₂', 'ppm'),
        (selected_habitat, 'cabin_o2', 'Cabin oxygen', '%'),
        ('simulation', 'acceleration', 'Acceleration (simulated)', 'g'),
    ]
    chart_columns = st.columns(2, gap="medium")
    for index, (entity, channel, title, unit) in enumerate(chart_specs):
        with chart_columns[index % 2]:
            st.markdown(f'<div class="dashboard-section-label">{escape(title)}</div>', unsafe_allow_html=True)
            if entity == 'simulation':
                history = g_history
            else:
                history = chart_sources.get(f'{entity}/{channel}', [])
            if not history or all(item['value'] is None for item in history):
                st.markdown('<div class="plain-svg-chart plain-svg-empty">No reliable readings</div>', unsafe_allow_html=True)
            else:
                svg = line_chart_svg([item['value'] for item in history], title, unit)
                st.markdown(f'<div class="plain-svg-chart">{svg}</div>', unsafe_allow_html=True)

    rad_history = st.session_state.setdefault('radiation_history_v25', {})
    selected_rad = radiation_rows['crews'].get(selected_crew)
    previous = rad_history.get(selected_crew, [])
    r_value = selected_rad['dose_equivalent_rate_uSv_h'] if selected_rad and selected_rad['quality'] == 'adequate' else None
    dose_value = selected_rad['cumulative_dose_uSv'] if selected_rad and selected_rad['quality'] == 'adequate' else None
    last_total = st.session_state.setdefault('radiation_last_total_v25', {})
    if dose_value is not None and selected_crew in last_total and dose_value < last_total[selected_crew]:
        r_value = None
        dose_value = None
        st.warning('Radiation counter reset or went backwards; confirm the exposure history before using the total.')
    if dose_value is not None:
        last_total[selected_crew] = dose_value
    elif selected_rad is None or selected_rad['quality'] != 'adequate':
        last_total.pop(selected_crew, None)
    stamp = len(previous)
    if selected_rad is not None:
        stamp = selected_rad.get('observed_elapsed_s') if selected_rad.get('observed_elapsed_s') is not None else stamp + 1
    rad_history[selected_crew] = trend_history(previous, selected_crew, 'radiation_rate', r_value, stamp, 60)
    totals = st.session_state.setdefault('radiation_total_history_v25', {})
    totals[selected_crew] = trend_history(totals.get(selected_crew, []), selected_crew, 'radiation_total', dose_value, stamp, 60)
    st.markdown('### Radiation trends')
    columns = st.columns(2)
    for col, title, key, unit in (
        (columns[0], 'Dose-equivalent rate', 'radiation_rate', 'µSv/h'),
        (columns[1], 'Accumulated dose', 'radiation_total', 'µSv')
    ):
        with col:
            st.markdown(f'<div class="dashboard-section-label">{escape(title)} · {escape(selected_crew)}</div>', unsafe_allow_html=True)
            rows = rad_history[selected_crew] if key == 'radiation_rate' else totals[selected_crew]
            svg = line_chart_svg([r['value'] for r in rows], title, unit)
            st.markdown(f'<div class="plain-svg-chart">{svg}</div>', unsafe_allow_html=True)

    with st.expander('Download sensor snapshots'):
        st.download_button('Download JSON', json.dumps({'schema': 'blindspot.dashboard.v2', 'synthetic': True,
                           'demo_event': scenario, 'crew': shown_crew, 'habitat': shown_habitat,
                           'flags': flags, 'radiation': radiation_rows}, indent=2), file_name='blindspot-dashboard-demo.json',
                           mime='application/json', key='multi-dashboard-download')


def _advance_eva(step_label: str):
    """Callback runs before widgets are instantiated during the next rerun."""
    st.session_state['eva_step'] = step_label


def mission_view():

    st.subheader("Mission overview")

    has_remote = bool(os.environ.get('BLINDSPOT_SENSOR_API_URL', '').strip())
    if has_remote:
        multi_crew_live_dashboard()
    else:
        st.info('Remote sensors are offline. Showing sample data.')
        try:
            local_meals = MealStore()
            meal_panel(local_meals, {name: local_meals.latest_meal(name) for name in CREW_IDS})
        except (OSError, sqlite3.Error, ValueError):
            st.error('Meal records unavailable. Check database permissions.')
    if has_remote:
        return
    scenario = st.selectbox("What's happening in the mission?", list(MISSION_SCENARIOS),
                            format_func=MISSION_SCENARIOS.get, key="mission-scenario")
    with st.expander("Advanced: repeatable simulation settings"):
        seed = st.number_input("Random seed", min_value=0, max_value=100000, value=42, step=1)
        duration = st.selectbox("Duration", [60, 120, 180], index=1,
                                format_func=lambda n: f"{n} seconds")
    requested = (scenario, int(seed), duration)
    if st.session_state.get('mission_config') != requested or 'mission_data' not in st.session_state:
        st.session_state.mission_data = generate_mission(scenario, int(seed), duration)
        st.session_state.mission_config = requested
    rows = st.session_state.mission_data
    point = max(r.second for r in rows)
    status = summarize(rows, point)
    severity, message = homepage_summary(status, scenario)
    if severity == 'warning':
        st.warning(message)
    elif severity == 'info':
        st.info(message)
    else:
        st.success(message)

    st.markdown('#### Astronaut and cabin at a glance')
    featured = ['heart_rate', 'spo2', 'cabin_co2', 'cabin_o2']
    featured = [k for k in featured if k in status]
    cols = st.columns(2)
    for i, key in enumerate(featured):
        value = status[key]
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{value['label']}**")
                st.metric('Measurement',
                          f"{value['value']:g} {value['unit']}" if value['value'] is not None else 'No reading',
                          label_visibility='collapsed')
                if value['quality'] == 'insufficient':
                    pass
                else:
                    pass
    with st.expander('See all crew and cabin measurements'):
        remaining = [(k, v) for k, v in status.items() if k not in featured]
        if not remaining:
            pass
        for _, value in remaining:
            formatted = f"{value['value']:g} {value['unit']}" if value['value'] is not None else 'Unavailable'
            st.write(f"**{value['label']}** · {formatted} · {value['quality']}")

    with st.expander('Explore data, quality checks, and downloads'):
        point = st.slider('Look back in the mission (seconds)', 0, point, point, 1)
        status = summarize(rows, point)
        trend = st.selectbox('Measurement to plot', list(CHANNELS),
                             format_func=lambda k: CHANNELS[k].label)
        plotted = [r.value if r.quality_flag == 'ok' else None
                   for r in rows if r.channel == trend and r.second <= point]
        if plotted:
            import streamlit.components.v1 as components
            components.html(chart_document(plotted, CHANNELS[trend].label, CHANNELS[trend].unit), height=236, scrolling=False)
        for value in status.values():
            st.write(f"**{value['label']}** — {value['quality']}; {value['explanation']}")
        receipt = telemetry_receipt(rows, scenario, int(seed), point)
        st.download_button('Download simulated evidence (JSON)',
                           json.dumps(receipt, indent=2),
                           file_name='blindspot-mission-evidence.json',
                           mime='application/json')

def eva_view():
    """Guided pre/post spacewalk demonstration with technical tools kept optional."""
    from blindspot.eva import SCENARIOS as EVA_SCENARIOS
    from blindspot.eva import METRICS, attach_pre_eva_camera, build_assessment, compare_assessments, decode_assessment
    from blindspot.navigation import eva_plain_stage, eva_outcome

    st.subheader('Spacewalk check')
    st.write('Compare readings taken before and after a spacewalk.')

    before = st.session_state.get('eva_pre')
    report = st.session_state.get('eva_report')
    title, instruction = eva_plain_stage(before is not None, report is not None)
    st.markdown(f'### {title}')

    if before is None:
        with st.container(border=True):
            crew_col, eva_col = st.columns(2)
            crew = crew_col.text_input('Astronaut ID', value='CREW-01', max_chars=40, key='eva-crew')
            eva_id = eva_col.text_input('Spacewalk ID', value='EVA-001', max_chars=40, key='eva-mission')
            if st.button('Save before-spacewalk reading', type='primary', key='eva-before-simple'):
                try:
                    st.session_state.eva_pre = build_assessment(crew, eva_id, 'pre', seed=42)
                    st.session_state.pop('eva_post', None)
                    st.session_state.pop('eva_report', None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with st.expander('Already have a saved reading? Import it here'):
            incoming = st.file_uploader('Before-spacewalk JSON', type=['json'], key='eva-import-pre-simple')
            if incoming is not None and st.button('Use uploaded reading', key='eva-use-pre-simple'):
                try:
                    payload = decode_assessment(incoming.getvalue())
                    if payload['phase'] != 'pre':
                        raise ValueError('This is not a before-spacewalk reading')
                    st.session_state.eva_pre = payload
                    st.session_state.pop('eva_post', None)
                    st.session_state.pop('eva_report', None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        return

    st.success(f"Before-spacewalk reading saved for {before['participant']} · {before['eva_id']}")
    with st.expander('What is this saved reading?'):
        st.write('Saved readings from before the spacewalk.')


        st.download_button('Save before-spacewalk file', json.dumps(before, indent=2),
                           file_name=f"before-{before['eva_id']}.json", mime='application/json', key='eva-save-before-simple')

    if report is None:
        st.write('Get the latest sensor readings or try a sample.')
        configured = bool(os.environ.get('BLINDSPOT_SENSOR_API_URL', '').strip())
        if configured:
            if st.button('Get readings from sensor simulator', type='primary', key='eva-fetch-simple'):
                try:
                    after = fetch_post_eva(os.environ['BLINDSPOT_SENSOR_API_URL'],
                                           os.environ.get('BLINDSPOT_SENSOR_TOKEN', ''),
                                           before['participant'], before['eva_id'], allow_http_local=True)
                    st.session_state.eva_report = compare_assessments(before, after)
                    st.session_state.eva_post = after
                    st.rerun()
                except (RemoteTelemetryError, ValueError) as exc:
                    st.error(f'Simulator data could not be used: {exc}')
        else:
            st.info('Remote sensors are offline. You can use sample data.')
        with st.container(border=True):
            scenario = st.selectbox('Example to try', list(EVA_SCENARIOS),
                                    format_func=EVA_SCENARIOS.get, key='eva-scenario-simple')
            if st.button('Compare sample readings', type='primary' if not configured else 'secondary',
                         key='eva-demo-simple'):
                try:
                    after = build_assessment(before['participant'], before['eva_id'], 'post', scenario, seed=42)
                    st.session_state.eva_report = compare_assessments(before, after)
                    st.session_state.eva_post = after
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with st.expander('Advanced: upload a sensor export instead'):
            incoming_post = st.file_uploader('After-spacewalk sensor JSON', type=['json'], key='eva-import-post-simple')
            if incoming_post is not None and st.button('Compare uploaded file', key='eva-use-post-simple'):
                try:
                    after = decode_assessment(incoming_post.getvalue())
                    st.session_state.eva_report = compare_assessments(before, after)
                    st.session_state.eva_post = after
                    st.rerun()
                except ValueError as exc:
                    st.error(f'Cannot compare: {exc}')
        if os.environ.get('BLINDSPOT_PUBLIC', '0') != '1':
            with st.expander('Optional: try a real local webcam test before the spacewalk'):
                camera_number = st.number_input('Camera number', 0, 9, key='eva-cam-index')
                hand = st.radio('Hand', ['Right', 'Left'], horizontal=True, key='eva-hand')
                if st.button('Measure 15 seconds of finger tapping', key='eva-record-taps'):
                    try:
                        policy = Protocol(hand=hand, close_ratio=0.34, open_ratio=0.56)
                        with st.spinner('Recording hand movements...'):
                            recording = capture(policy, camera_index=int(camera_number))
                        scored = assess(recording.frames, policy, recording.duration_s)
                        payload = {'count': scored.count, 'duration_s': scored.duration_s,
                                   'coverage': scored.evidence.coverage,
                                   'sufficient': scored.evidence.sufficient,
                                   'protocol_id': policy.fingerprint}
                        st.session_state.eva_pre = attach_pre_eva_camera(before, taps=payload)
                        st.success(f'{scored.count} cycles counted · {scored.evidence.coverage:.0%} tracking')
                    except (CameraUnavailable, ValueError) as exc:
                        st.error(str(exc))
                if st.button('Measure 8 seconds of eye movement', key='eva-record-eyes'):
                    from blindspot.eye import EyeCameraUnavailable, capture_eye_motion
                    try:
                        with st.spinner('Recording approximate pupil movement...'):
                            eye = capture_eye_motion(8.0, int(camera_number))
                        current = st.session_state.get('eva_pre', before)
                        st.session_state.eva_pre = attach_pre_eva_camera(current, eye=eye)
                        st.info(f"Eye-motion tracking coverage: {eye['coverage']:.0%}; this is not a calibrated gaze test.")
                    except (EyeCameraUnavailable, ValueError) as exc:
                        st.error(str(exc))
        return

    status = report['overall']
    summary = eva_outcome(status)
    if status == 'insufficient_evidence':
        st.warning(summary)
    elif status == 'changes_observed':
        st.info(summary)
    else:
        st.success(summary)
    st.write(report['interpretation'])
    a, b = st.columns(2)
    a.metric('Measurements with changes', report['changed_channels'])
    b.metric('Measurements needing checking', report['missing_or_unreliable_channels'])
    with st.expander('See every measurement and the reason'):
        for group in sorted({m.group for m in METRICS.values()}):
            st.markdown(f'**{group}**')
            for key, metric in METRICS.items():
                if metric.group != group:
                    continue
                item = report['metrics'][key]
                if item['status'] in ('insufficient_evidence', 'different_measurement_sources'):
                    st.write(f"{metric.label}: cannot compare ({'; '.join(item['reasons'])})")
                else:
                    st.write(f"{metric.label}: before {item['pre']:g} {metric.unit} → after {item['post']:g} {metric.unit} · {item['status'].replace('_', ' ')}")
        for name, item in report.get('camera_checks', {}).items():
            st.write(f"Camera {name}: {item['status'].replace('_', ' ')}. {item['note']}")
    receipt = {'comparison': report, 'pre': before, 'post': st.session_state.get('eva_post')}
    st.download_button('Download comparison report', json.dumps(receipt, indent=2),
                       file_name=f"eva-evidence-{report['eva_id']}.json", mime='application/json', key='eva-receipt-simple')
    if st.button('Start another spacewalk check', key='eva-reset-simple'):
        for key in ('eva_pre', 'eva_post', 'eva_report'):
            st.session_state.pop(key, None)
        st.rerun()


def _set_main_page(page: str):

    st.session_state["main_page"] = page


def main():
    public = os.environ.get("BLINDSPOT_PUBLIC", "0") == "1"
    st.set_page_config(page_title="BLINDSPOT · Spacewalk Health", page_icon="◉", layout="wide")
    st.markdown(f"<style>{stylesheet()}</style>", unsafe_allow_html=True)

    st.markdown(
        '<style>'
        '[data-testid="stMainBlockContainer"], .block-container {'
        'max-width: min(96vw, 1800px) !important;'
        'padding-left: clamp(1rem, 2vw, 2.5rem) !important;'
        'padding-right: clamp(1rem, 2vw, 2.5rem) !important;'
        '}'
        '</style>',
        unsafe_allow_html=True,
    )
    header_left, header_right = st.columns([8, 2], vertical_alignment="top")
    with header_left:
        st.title("BLINDSPOT")
        st.markdown("**SIMULATED SENSOR DATA**")
    with header_right:
        if st.session_state.get("main_page", "Mission overview") == "Mission overview":
            with st.popover('🎛 Demo', use_container_width=True):
                st.selectbox('Trigger event', list(DEMO_SCENARIOS),
                             format_func=DEMO_SCENARIOS.get, key='demo_event')
                st.selectbox('Astronaut', ['CREW-01', 'CREW-02', 'CREW-03'],
                             key='demo_crew')
                st.button('Clear demo', key='clear-demo', on_click=_clear_demo,
                          use_container_width=True)
    pages = ["Mission overview", "Spacewalk check", "More"]
    selected_page = st.session_state.get("main_page", pages[0])
    if selected_page not in pages:
        selected_page = pages[0]
        st.session_state["main_page"] = selected_page
    nav_columns = st.columns([1.2, 1.2, 0.7, 5], gap="small")
    for column, label in zip(nav_columns, pages):
        with column:
            st.button(label, key=f"nav-{label}",
                      type="primary" if selected_page == label else "secondary",
                      on_click=_set_main_page, args=(label,), use_container_width=True)
    page = selected_page
    st.divider()
    if page == "Mission overview":
        mission_view()
    elif page == "Spacewalk check":
        eva_view()
    else:
        st.subheader("More")
        st.info("Research demo only. Not for medical or flight decisions.")
        options = ["Fault lab", "Research"] if public else ["Food Management", "Webcam assessment", "Fault lab", "Saved sessions", "Research"]
        choice = st.selectbox("Choose a tool", options)
        if choice == "Research":
            research_view()
        elif choice == "Food Management":
            food_management_view()
        else:
            try:
                with SessionStore(":memory:" if public else Path(os.environ.get("BLINDSPOT_DB", "data/blindspot.db"))) as store:
                    if choice == "Webcam assessment":
                        assessment_view(store)
                    elif choice == "Fault lab":
                        lab_view(store)
                    else:
                        history_view(store)
            except (sqlite3.Error, OSError):
                st.error("Session storage unavailable; check folder permissions.")
    st.divider()
