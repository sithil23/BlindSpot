"""Eligible-session baseline and descriptive change; never a diagnostic classifier."""

import time
from dataclasses import asdict, dataclass, field
from statistics import median
from uuid import uuid4

from blindspot import __version__
from blindspot.models import Assessment, Evidence, Protocol
from blindspot.nasa import research_context


@dataclass(frozen=True)
class Comparison:
    status: str
    explanation: str
    baseline_ids: tuple[str, ...] = ()
    baseline_hz: float | None = None
    change_percent: float | None = None


@dataclass(frozen=True)
class Session:
    id: str
    participant: str
    source: str
    created_at: float
    protocol_id: str
    assessment: Assessment
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(cls, participant, source, policy, assessment, created_at=None, metadata=None):
        if source not in ("webcam", "synthetic"):
            raise ValueError("Unknown source")
        if not participant.strip() or len(participant.strip()) > 64:
            raise ValueError("Use a participant code of 1 to 64 characters")
        return cls(
            str(uuid4()),
            participant.strip(),
            source,
            time.time() if created_at is None else created_at,
            policy.fingerprint,
            assessment,
            metadata or {},
        )

    def receipt(self, comparison: Comparison, policy: Protocol) -> dict:
        return {
            "schema_version": 1,
            "app_version": __version__,
            **asdict(self),
            "policy": asdict(policy),
            "comparison": asdict(comparison),
            "research_context": research_context(),
            "limitations": "Engineering demonstration only. Not a diagnosis, fitness-for-duty "
            "assessment, or validated astronaut health monitor.",
            "raw_video_stored": False,
        }

    @classmethod
    def from_dict(cls, data: dict):
        data = dict(data)
        result = dict(data.pop("assessment"))
        evidence = dict(result.pop("evidence"))
        evidence["reasons"] = tuple(evidence["reasons"])
        result["tap_times"] = tuple(result["tap_times"])
        return cls(**data, assessment=Assessment(**result, evidence=Evidence(**evidence)))


def compare(current: Session, history: list[Session], policy: Protocol) -> Comparison:
    if not current.assessment.evidence.sufficient:
        return Comparison(
            "insufficient_evidence",
            "Insufficient evidence. Observed count is incomplete or unreliable; "
            "a performance change cannot be inferred. Repeat with clear tracking.",
        )
    eligible = {
        s.id: s
        for s in history
        if s.id != current.id
        and s.participant == current.participant
        and s.source == current.source
        and s.protocol_id == current.protocol_id == policy.fingerprint
        and 0 < current.created_at - s.created_at <= policy.baseline_max_age_days * 86400
        and s.assessment.protocol_id == current.protocol_id
        and s.assessment.evidence.sufficient
        and s.assessment.rate_hz is not None
    }
    prior = sorted(eligible.values(), key=lambda s: s.created_at, reverse=True)[:20]
    prior.sort(key=lambda s: s.created_at)
    ids = tuple(s.id for s in prior)
    if len(prior) < policy.minimum_baselines:
        return Comparison(
            "baseline_needed",
            f"Tracking meets prototype settings. Record "
            f"{policy.minimum_baselines - len(prior)} more eligible prior "
            "session(s) for a personal comparison.",
            ids,
        )
    baseline = median(s.assessment.rate_hz for s in prior if s.assessment.rate_hz is not None)
    rate = current.assessment.rate_hz
    change = 100 * (rate - baseline) / baseline if baseline > 0 and rate is not None else None
    text = (
        f"Observed tapping rate is {abs(change):.1f}% "
        f"{'below' if change < 0 else 'above'} the personal median. "
        if change is not None and abs(change) >= 0.05
        else "Observed tapping rate matches the personal median. "
        if change is not None
        else "Personal median is zero; a percentage change is undefined. "
    )
    return Comparison(
        "comparable",
        text + "Descriptive comparison only; cause and medical significance cannot be determined.",
        ids,
        baseline,
        change,
    )
