"""Pure display scheduling; the camera measurement loop must not wait on UI rendering."""


def should_update(now_s: float, last_update_s: float, interval_s: float) -> bool:
    if interval_s <= 0:
        raise ValueError("interval_s must be positive")
    return last_update_s < 0 or now_s - last_update_s >= interval_s
