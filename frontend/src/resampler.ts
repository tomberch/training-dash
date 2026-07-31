export interface FitRecord {
  distance_m: number;
  hr_bpm: number | null;
  power_w: number | null;
  speed_mps: number | null;
  altitude_m: number | null;
}

export const BUCKET_SIZE_M = 50;

export function resampleByDistance(records: FitRecord[]): FitRecord[] {
  if (records.length === 0) return [];
  const maxDist = records[records.length - 1].distance_m;
  if (maxDist <= 0) return [withDistance(records[0], 0)];

  const numBuckets = Math.floor(maxDist / BUCKET_SIZE_M);
  const buckets: FitRecord[] = [];

  for (let b = 0; b <= numBuckets; b++) {
    const targetDist = b * BUCKET_SIZE_M;
    buckets.push(interpolateAt(records, targetDist));
  }

  return buckets;
}

function interpolateAt(records: FitRecord[], targetDist: number): FitRecord {
  if (records.length === 0) {
    return makeRecord(targetDist);
  }

  if (targetDist <= records[0].distance_m) return withDistance(records[0], targetDist);

  const last = records[records.length - 1];
  if (targetDist >= last.distance_m) return withDistance(last, targetDist);

  let lo = 0;
  let hi = records.length - 1;
  while (lo < hi - 1) {
    const mid = Math.floor((lo + hi) / 2);
    if (records[mid].distance_m <= targetDist) lo = mid;
    else hi = mid;
  }

  const r0 = records[lo];
  const r1 = records[hi];
  const span = r1.distance_m - r0.distance_m;
  const t = span > 0 ? (targetDist - r0.distance_m) / span : 0;

  return makeRecord(
    targetDist,
    lerp(r0.hr_bpm, r1.hr_bpm, t),
    lerp(r0.power_w, r1.power_w, t),
    lerp(r0.speed_mps, r1.speed_mps, t),
    lerp(r0.altitude_m, r1.altitude_m, t),
  );
}

function makeRecord(
  distance_m: number,
  hr_bpm: number | null = null,
  power_w: number | null = null,
  speed_mps: number | null = null,
  altitude_m: number | null = null,
): FitRecord {
  return { distance_m, hr_bpm, power_w, speed_mps, altitude_m };
}

function withDistance(r: FitRecord, dist: number): FitRecord {
  return makeRecord(dist, r.hr_bpm, r.power_w, r.speed_mps, r.altitude_m);
}

function lerp(a: number | null, b: number | null, t: number): number | null {
  if (a === null && b === null) return null;
  if (a === null) return b;
  if (b === null) return a;
  return a + (b - a) * t;
}