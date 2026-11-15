



from __future__ import annotations

CREW_CHANNELS = ('heart_rate', 'spo2', 'respiration', 'body_temp')


def crew_summary(payload: dict | None) -> dict:
    if payload is None:
        return {key: None for key in CREW_CHANNELS}
    channels = payload['channels']
    return {key: (channels[key]['value'] if channels[key]['quality'] == 'adequate' else None)
            for key in CREW_CHANNELS}


def dashboard_flags(crew_feeds: dict[str, dict | None], habitat_feeds: dict[str, dict | None]) -> list[dict[str, str]]:
    """Warnings indicate evidence gaps and descriptive trends, never health diagnoses."""
    result = []
    if (len(crew_feeds) >= 2 and all(payload is None for payload in crew_feeds.values())
            and len(habitat_feeds) >= 1 and all(payload is None for payload in habitat_feeds.values())):
        result.append({'kind': 'critical',
                       'message': 'All crew and habitat monitoring feeds are unavailable. Check sensor connections.'})
    for crew, payload in crew_feeds.items():
        if payload is None:
            result.append({'kind': 'feed', 'message': f'{crew}: sensor feed unavailable; no readings inferred.'})
            continue
        for key in CREW_CHANNELS:
            channel = payload['channels'][key]
            if channel['quality'] != 'adequate':
                result.append({'kind': 'evidence', 'message': f'{crew}: {channel["label"]} is missing or stale. Check evidence.'})
        if payload['scenario'] == 'exercise':
            result.append({'kind': 'context', 'message': f'{crew}: simulated exercise context. Changes are descriptive only.'})
    for source, payload in habitat_feeds.items():
        if payload is None:
            result.append({'kind': 'feed', 'message': f'{source}: habitat feed unavailable; no readings inferred.'})
            continue
        co2 = payload['channels']['cabin_co2']
        if co2['quality'] != 'adequate':
            result.append({'kind': 'evidence', 'message': f'{source}: cabin CO₂ reading unavailable. Verify the feed.'})
        elif co2['trend'] == 'rising':
            result.append({'kind': 'trend', 'message': f'{source}: simulated cabin CO₂ is rising. Investigate the trend and verify the sensor.'})
    return result
