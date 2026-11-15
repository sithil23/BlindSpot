"""Crew follow-up ordering for the demonstration dashboard."""

from __future__ import annotations

from math import isfinite
import re

CHANNELS = ('heart_rate', 'spo2', 'respiration', 'body_temp')


def rank_crew(feeds: dict, flags: list[dict]) -> list[dict]:
    """Order synthetic crew feeds by monitoring follow-up, not medical urgency."""
    ranked = []
    for crew_id, payload in feeds.items():
        stats = {}
        missing = []
        for name in CHANNELS:
            channel = (payload or {}).get('channels', {}).get(name)
            value = channel.get('value') if isinstance(channel, dict) else None
            valid = (isinstance(channel, dict) and channel.get('quality') == 'adequate'
                     and isinstance(value, (int, float)) and not isinstance(value, bool)
                     and isfinite(value))
            stats[name] = value if valid else None
            if not valid:
                missing.append(name)

        own_flags = [
            flag for flag in flags
            if re.match(rf'^(?:DEMO · )?{re.escape(crew_id)}(?=[: ])', flag.get('message', ''))
        ]
        health_flags = [
            flag for flag in own_flags
            if flag.get('kind') == 'warning'
            and ('reading is ' in flag.get('message', '')
                 or 'breathing rate is high' in flag.get('message', ''))
        ]
        if payload is None:
            level, state, score = 'Data missing', 'Check sensor feed', 2
        elif missing:
            level, state, score = 'Data incomplete', 'Check measurement', 2
        elif health_flags:
            level, state, score = 'Flagged', 'Review sensor reading', 3
        else:
            level, state, score = 'No crew flags', 'No flagged crew readings', 0
        if health_flags and not missing:
            medical = 'Review flagged reading'
        elif missing:
            medical = 'Not assessable'
        else:
            medical = 'No flagged measurement'

        ranked.append({
            'crew_id': crew_id, 'score': score, 'level': level, 'state': state,
            'stats': stats, 'medical': medical, 'rest': 'Not assessed',
            'exercise': 'Exercise context recorded' if (payload or {}).get('scenario') == 'exercise' else 'Not assessed',
            'sleep': 'Not assessed',
        })
    return sorted(ranked, key=lambda row: (-row['score'], row['crew_id']))[:3]


def priority_alert(item: dict) -> dict:
    flagged = item.get('level') == 'Flagged' and item.get('medical') != 'Not assessable'
    return {
        'highlight': flagged,
        'message': 'Crew review requested' if flagged else ''
    }


def crew_report(item: dict) -> dict:
    return {
        'schema': 'blindspot.crew_review.v1',
        'synthetic': True,
        'crew_id': item.get('crew_id'),
        'priority': item.get('level'),
        'reason': item.get('state'),
        'stats': item.get('stats', {}),
        'delivery_status': 'not_sent',
        'requires_human_review': True,
    }
