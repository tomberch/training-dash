export interface ResampleInput {
  distance_m: number;
  hr_bpm: number | null;
  power_w: number | null;
  speed_mps: number | null;
  altitude_m: number | null;
}

export interface ResampleOutput {
  distance_m: number;
  hr_bpm: number | null;
  power_w: number | null;
  speed_mps: number | null;
  altitude_m: number | null;
}

export const BUCKET_SIZE_M = 50;

export function resampleByDistance(
  records: ResampleInput[],
  bucketSizeM: number = BUCKET_SIZE_M
): ResampleOutput[] {
  if (records.length === 0) return [];
  const maxDist = records[records.length - 1].distance_m;
  if (maxDist <= 0) return [records[0]];

  const numBuckets = Math.floor(maxDist / bucketSizeM);
  const buckets: ResampleOutput[] = [];

  for (let b = 0; b <= numBuckets; b++) {
    const targetDist = b * bucketSizeM;
    buckets.push(interpolateAt(records, targetDist));
  }

  return buckets;
}

function interpolateAt(
  records: ResampleInput[],
  targetDist: number
): ResampleOutput {
  if (records.length === 0) {
    return { distance_m: targetDist, hr_bpm: null, power_w: null, speed_mps: null, altitude_m: null };
  }

  if (targetDist <= records[0].distance_m) return snapTo(records[0], targetDist);

  const last = records[records.length - 1];
  if (targetDist >= last.distance_m) return snapTo(last, targetDist);

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

  return {
    distance_m: targetDist,
    hr_bpm: lerp(r0.hr_bpm, r1.hr_bpm, t),
    power_w: lerp(r0.power_w, r1.power_w, t),
    speed_mps: lerp(r0.speed_mps, r1.speed_mps, t),
    altitude_m: lerp(r0.altitude_m, r1.altitude_m, t),
  };
}

function snapTo(r: ResampleInput, dist: number): ResampleOutput {
  return {
    distance_m: dist,
    hr_bpm: r.hr_bpm,
    power_w: r.power_w,
    speed_mps: r.speed_mps,
    altitude_m: r.altitude_m,
  };
}

function lerp(a: number | null, b: number | null, t: number): number | null {
  if (a === null && b === null) return null;
  if (a === null) return b;
  if (b === null) return a;
  return a + (b - a) * t;
}