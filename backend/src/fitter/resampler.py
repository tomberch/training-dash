BUCKET_SIZE_M = 50


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
        return {"distance_m": target_dist, "timestamp_s": 0.0}

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
    return {"distance_m": target_dist, "timestamp_s": ts}


def _with_distance(r: dict, dist: float) -> dict:
    return {"distance_m": dist, "timestamp_s": r["timestamp_s"]}


def _lerp(a: float, b: float, t: float) -> float:
    if a is None or b is None:
        return a if a is not None else b
    return a + (b - a) * t


def compute_time_gap_series(
    records_a: list[dict],
    records_b: list[dict],
    bucket_size_m: int = BUCKET_SIZE_M,
) -> list[dict]:
    resampled_a = resample_by_distance(records_a, bucket_size_m)
    resampled_b = resample_by_distance(records_b, bucket_size_m)

    min_len = min(len(resampled_a), len(resampled_b))
    series = []
    for i in range(min_len):
        gap = resampled_a[i]["timestamp_s"] - resampled_b[i]["timestamp_s"]
        series.append({"distance_m": resampled_a[i]["distance_m"], "gap_s": gap})
    return series