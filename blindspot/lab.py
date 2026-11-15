

from blindspot.assessment import assess
from blindspot.models import Protocol
from blindspot.sessions import Session, compare
from blindspot.synthetic import make_demo


def run_lab(scenario: str, policy: Protocol | None = None):
    policy = policy or Protocol()
    frames = make_demo(scenario, policy)
    current = Session.create(
        "DEMO",
        "synthetic",
        policy,
        assess(frames, policy, policy.duration_s),
        metadata={"scenario": scenario, "generator": "plateau-2hz-v1"},
    )
    prior = [
        Session.create(
            "DEMO",
            "synthetic",
            policy,
            assess(make_demo("clean", policy), policy, policy.duration_s),
            current.created_at - seconds,
            metadata={"fixture": True},
        )
        for seconds in (60, 40, 20)
    ]
    comparison = compare(current, prior, policy)
    baseline = prior[0].assessment.rate_hz
    basic = (
        "No observed measurement."
        if current.assessment.rate_hz is None
        else f"Observed rate: {current.assessment.rate_hz:.2f} cycles/s. "
        f"{100 * (current.assessment.rate_hz / baseline - 1):+.1f}% versus clean reference. "
        "A count-only monitor might label this a performance change."
    )
    receipt = current.receipt(comparison, policy)
    receipt["lab_reference_sessions"] = [s.receipt(compare(s, [], policy), policy) for s in prior]
    return current, frames, comparison, receipt, basic
