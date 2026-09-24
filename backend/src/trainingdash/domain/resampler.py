BUCKET_SIZE_M = 50

# Speed threshold for "stopped" detection (m/s). Below this, time doesn't count as moving.
STOPPED_SPEED_THRESHOLD = 0.5


def resample_by_distance(
    records: list[dict],
    bucket_size_m: int = BUCKET_SIZE_M,
) -> list[dict]:
    if not records:
        return []
    max_dist = records[-1]["distance_m"]
    if max_dist <= 0:
        return [dict(records[0])]

    num_buckets = int(max_dist // bucket_size_m)
    buckets = []
    for b in range(num_buckets + 1):
        target = b * bucket_size_m
        buckets.append(_interpolate_at(records, target))
    return buckets


def _interpolate_at(records: list[dict], target_dist: float) -> dict:
    if not records:
        return {"distance_m": target_dist, "timestamp_s": 0.0, "moving_time_s": 0.0}

    if target_dist <= records[0]["distance_m"]:
        return _with_distance(records[0], target_dist)

    last = records[-1]
    if target_dist >= last["distance_m"]:
        return _with_distance(last, target_dist)

    lo, hi = 0, len(records) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if records[mid]["distance_m"] <= target_dist:
            lo = mid
        else:
            hi = mid

    r0, r1 = records[lo], records[hi]
    span = r1["distance_m"] - r0["distance_m"]
    t = (target_dist - r0["distance_m"]) / span if span > 0 else 0
    ts = _lerp(r0["timestamp_s"], r1["timestamp_s"], t)
    moving_ts = _lerp(r0.get("moving_time_s", r0["timestamp_s"]), r1.get("moving_time_s", r1["timestamp_s"]), t)
    return {"distance_m": target_dist, "timestamp_s": ts, "moving_time_s": moving_ts}


def _with_distance(r: dict, dist: float) -> dict:
    return {
        "distance_m": dist,
        "timestamp_s": r["timestamp_s"],
        "moving_time_s": r.get("moving_time_s", r["timestamp_s"]),
    }


def _lerp(a: float, b: float, t: float) -> float:
    if a is None or b is None:
        return a if a is not None else b
    return a + (b - a) * t


def compute_time_gap_series(
    records_a: list[dict],
    records_b: list[dict],
    bucket_size_m: int = BUCKET_SIZE_M,
) -> list[dict]:
    """Compute elapsed time gap series (legacy, for backward compatibility)."""
    resampled_a = resample_by_distance(records_a, bucket_size_m)
    resampled_b = resample_by_distance(records_b, bucket_size_m)

    min_len = min(len(resampled_a), len(resampled_b))
    series = []
    for i in range(min_len):
        gap = resampled_a[i]["timestamp_s"] - resampled_b[i]["timestamp_s"]
        series.append({"distance_m": resampled_a[i]["distance_m"], "gap_s": gap})
    return series


def compute_time_gap_series_dual(
    records_a: list[dict],
    records_b: list[dict],
    bucket_size_m: int = BUCKET_SIZE_M,
) -> tuple[list[dict], list[dict]]:
    """Compute both elapsed and moving time gap series.

    Returns (elapsed_gap_series, moving_gap_series).
    Each series contains [{distance_m, gap_s}, ...].
    """
    resampled_a = resample_by_distance(records_a, bucket_size_m)
    resampled_b = resample_by_distance(records_b, bucket_size_m)

    min_len = min(len(resampled_a), len(resampled_b))
    elapsed_series = []
    moving_series = []
    for i in range(min_len):
        dist = resampled_a[i]["distance_m"]
        elapsed_gap = resampled_a[i]["timestamp_s"] - resampled_b[i]["timestamp_s"]
        moving_gap = resampled_a[i]["moving_time_s"] - resampled_b[i]["moving_time_s"]
        elapsed_series.append({"distance_m": dist, "gap_s": elapsed_gap})
        moving_series.append({"distance_m": dist, "gap_s": moving_gap})
    return elapsed_series, moving_series


def compute_moving_time(records: list[dict], speed_threshold: float = STOPPED_SPEED_THRESHOLD) -> list[dict]:
    """Add cumulative moving_time_s to records based on speed.

    Takes records with {distance_m, timestamp_s, speed_mps} and returns
    records with added moving_time_s field.

    Uses the same algorithm as FIT ingest: a record counts as "moving" if its
    speed exceeds the threshold. Time intervals are capped at 30s to avoid
    counting pauses.
    """
    if not records:
        return []

    result = []
    cumulative_moving = 0.0
    max_interval = 30.0  # Cap intervals to avoid counting long pauses

    for i, r in enumerate(records):
        if i == 0:
            result.append({**r, "moving_time_s": 0.0})
            continue

        prev = records[i - 1]
        elapsed = r["timestamp_s"] - prev["timestamp_s"]

        # Current record counts as moving if speed exceeds threshold
        speed_curr = r.get("speed_mps") or 0.0
        if speed_curr > speed_threshold:
            # Cap interval to avoid counting pauses as moving
            cumulative_moving += min(elapsed, max_interval)

        result.append({**r, "moving_time_s": cumulative_moving})

    return result
