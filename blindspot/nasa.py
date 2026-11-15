"""Offline NASA research adapter: provenance, task rationale and explicit boundaries."""

import json
from hashlib import sha256
from importlib.resources import files


def research_context() -> dict:
    raw = files("blindspot").joinpath("data/nasa_context.json").read_bytes()
    return {**json.loads(raw), "content_sha256": sha256(raw).hexdigest()}
