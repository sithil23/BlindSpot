

import argparse
import json
from pathlib import Path

from blindspot.assessment import assess
from blindspot.camera import DEFAULT_MODEL, CameraUnavailable, capture, prepare_model
from blindspot.lab import run_lab
from blindspot.models import Protocol
from blindspot.sessions import Session, compare
from blindspot.storage import SessionStore
from blindspot.synthetic import SCENARIOS


def main(argv=None):
    parser = argparse.ArgumentParser(description="BLINDSPOT evidence-aware tapping prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run a deterministic offline fault demonstration")
    demo.add_argument("--scenario", choices=SCENARIOS, default="tracking_loss")
    demo.add_argument("--output", type=Path, help="Write an evidence receipt JSON")
    prepare = commands.add_parser("prepare-camera", help="Download the hand model once")
    prepare.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    webcam = commands.add_parser("capture", help="Run local webcam assessment without dashboard")
    webcam.add_argument("--participant", default="P01")
    webcam.add_argument("--hand", choices=["Left", "Right"], default="Right")
    webcam.add_argument("--camera", type=int, default=0)
    webcam.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    webcam.add_argument("--db", type=Path, default=Path("data/blindspot.db"))
    webcam.add_argument("--save", action="store_true", help="Explicitly save summary and receipt")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-camera":
            print(f"Model ready: {args.model}\nSHA256: {prepare_model(args.model)}")
        elif args.command == "demo":
            _, _, _, receipt, basic = run_lab(args.scenario)
            print("SYNTHETIC DEMONSTRATION\nBasic monitor: " + basic)
            print("BLINDSPOT: " + receipt["comparison"]["explanation"])
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8"
                )
                print(f"Receipt: {args.output}")
        else:
            policy = Protocol(hand=args.hand)
            if not args.participant.strip():
                parser.error("Participant code is required")
            print(f"Hold one {args.hand.lower()} hand in view. Start tapping for 15 seconds.")
            captured = capture(policy, args.model, args.camera)
            session = Session.create(
                args.participant,
                "webcam",
                policy,
                assess(captured.frames, policy, captured.duration_s),
                metadata=captured.metadata,
            )
            with SessionStore(args.db) as store:
                comparison = compare(session, store.baseline_candidates(session, policy), policy)
                receipt = session.receipt(comparison, policy)
                if args.save:
                    store.save(session, receipt)
            print(json.dumps(receipt, indent=2, allow_nan=False))
    except (CameraUnavailable, OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    return 0
