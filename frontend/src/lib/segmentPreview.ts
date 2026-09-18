/**
 * Client-side segment preview geometry.
 *
 * Mirrors the backend's `segment_geometry` computation so the creation modal
 * can show live distance / elevation / grade stats and a gradient profile
 * before the segment is actually created. The authoritative values are still
 * computed server-side on create.
 */

import type { GeoJSONFeature, ElevationPoint } from "@/api";
import type { ClimbCategory } from "@/api/segments";

export interface PreviewStats {
  distance_m: number;
  elevation_gain_m: number;
  avg_grade_pct: number;
  max_grade_pct: number;
  elevation_profile: ElevationPoint[];
  type: "climb" | "sprint" | "custom";
  climb_category: ClimbCategory | null;
}

const GRADIENT_SEGMENT_LENGTH_M = 50;

// Type classification thresholds (mirrors CreateSegment use case)
const CLIMB_MIN_GRADE_PCT = 3.0;
const CLIMB_MIN_LENGTH_M = 300.0;
const SPRINT_MIN_LENGTH_M = 150.0;
const SPRINT_MAX_LENGTH_M = 600.0;
const SPRINT_MAX_GRADE_PCT = 3.0;
const SPRINT_MIN_GRADE_PCT = -3.0;

function haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** A valid GPS feature with its index into the original feature array. */
interface ValidFeature {
  index: number;
  lat: number;
  lng: number;
  altitude_m: number | null;
  distance_m: number;
}

function toValidFeatures(features: GeoJSONFeature[]): ValidFeature[] {
  return features
    .map((f, index) => ({ f, index }))
    .filter(({ f }) => f.geometry !== null && f.geometry.coordinates.length >= 2)
    .map(({ f, index }) => ({
      index,
      lng: f.geometry!.coordinates[0],
      lat: f.geometry!.coordinates[1],
      altitude_m: f.properties.altitude_m,
      distance_m: f.properties.distance_m,
    }));
}

export function categorizeClimb(distance_m: number, avg_grade_pct: number): ClimbCategory {
  const score = distance_m * avg_grade_pct;
  if (score >= 80000) return "hc";
  if (score >= 64000) return "1";
  if (score >= 32000) return "2";
  if (score >= 16000) return "3";
  if (score >= 8000) return "4";
  return "nc";
}

function classify(distance_m: number, avg_grade_pct: number): {
  type: "climb" | "sprint" | "custom";
  climb_category: ClimbCategory | null;
} {
  if (avg_grade_pct >= CLIMB_MIN_GRADE_PCT && distance_m >= CLIMB_MIN_LENGTH_M) {
    return { type: "climb", climb_category: categorizeClimb(distance_m, avg_grade_pct) };
  }
  if (
    distance_m >= SPRINT_MIN_LENGTH_M &&
    distance_m <= SPRINT_MAX_LENGTH_M &&
    avg_grade_pct >= SPRINT_MIN_GRADE_PCT &&
    avg_grade_pct <= SPRINT_MAX_GRADE_PCT
  ) {
    return { type: "sprint", climb_category: null };
  }
  return { type: "custom", climb_category: null };
}

/**
 * Compute a preview of the segment between two feature indices (inclusive).
 * Returns null when the range doesn't contain enough valid GPS points.
 */
export function computeSegmentPreview(
  features: GeoJSONFeature[],
  startIndex: number,
  endIndex: number
): PreviewStats | null {
  const range = features.slice(startIndex, endIndex + 1);
  const valid = toValidFeatures(range);
  if (valid.length < 2) return null;

  const points = valid.map((v) => ({ lat: v.lat, lng: v.lng }));

  // Distance: prefer cumulative distance_m delta, fall back to haversine sum.
  let distance_m = valid[valid.length - 1].distance_m - valid[0].distance_m;
  if (distance_m <= 0) {
    distance_m = 0;
    for (let i = 1; i < points.length; i++) {
      distance_m += haversineDistance(points[i - 1].lat, points[i - 1].lng, points[i].lat, points[i].lng);
    }
  }

  // Elevation stats
  const withAlt = valid.filter((v) => v.altitude_m !== null);
  let elevation_gain_m = 0;
  let max_grade_pct = 0;
  let avg_grade_pct = 0;

  if (withAlt.length >= 2) {
    for (let i = 1; i < withAlt.length; i++) {
      const deltaAlt = withAlt[i].altitude_m! - withAlt[i - 1].altitude_m!;
      if (deltaAlt > 0) elevation_gain_m += deltaAlt;
      const deltaDist = withAlt[i].distance_m - withAlt[i - 1].distance_m;
      if (deltaDist > 0) {
        const grade = (deltaAlt / deltaDist) * 100;
        if (grade > max_grade_pct) max_grade_pct = grade;
      }
    }
    const totalAlt = withAlt[withAlt.length - 1].altitude_m! - withAlt[0].altitude_m!;
    const totalDist = withAlt[withAlt.length - 1].distance_m - withAlt[0].distance_m;
    avg_grade_pct = totalDist > 0 ? (totalAlt / totalDist) * 100 : 0;
  }

  // Elevation profile at fixed intervals (ElevationPoint format)
  const elevation_profile: ElevationPoint[] = [];
  if (withAlt.length >= 2) {
    const baseDistance = withAlt[0].distance_m;
    let segStartDist = withAlt[0].distance_m;
    let segStartAlt = withAlt[0].altitude_m!;
    
    // Add first point
    elevation_profile.push({
      distance_m: 0,
      elevation_m: segStartAlt,
      grade_pct: 0,
    });
    
    for (let i = 1; i < withAlt.length; i++) {
      const segDist = withAlt[i].distance_m - segStartDist;
      if (segDist >= GRADIENT_SEGMENT_LENGTH_M) {
        const deltaAlt = withAlt[i].altitude_m! - segStartAlt;
        const grade = segDist > 0 ? (deltaAlt / segDist) * 100 : 0;
        elevation_profile.push({
          distance_m: withAlt[i].distance_m - baseDistance,
          elevation_m: withAlt[i].altitude_m!,
          grade_pct: Math.round(grade * 10) / 10,
        });
        segStartDist = withAlt[i].distance_m;
        segStartAlt = withAlt[i].altitude_m!;
      }
    }
    
    // Add last point if not already included
    const lastPoint = withAlt[withAlt.length - 1];
    const lastProfilePoint = elevation_profile[elevation_profile.length - 1];
    if (lastProfilePoint.distance_m !== lastPoint.distance_m - baseDistance) {
      const remaining = lastPoint.distance_m - segStartDist;
      const deltaAlt = lastPoint.altitude_m! - segStartAlt;
      const grade = remaining > 0 ? (deltaAlt / remaining) * 100 : 0;
      elevation_profile.push({
        distance_m: lastPoint.distance_m - baseDistance,
        elevation_m: lastPoint.altitude_m!,
        grade_pct: Math.round(grade * 10) / 10,
      });
    }
  }

  const { type, climb_category } = classify(distance_m, avg_grade_pct);

  return {
    distance_m,
    elevation_gain_m,
    avg_grade_pct,
    max_grade_pct,
    elevation_profile,
    type,
    climb_category,
  };
}

/** Find the index of the valid GPS feature closest to the given map click. */
export function nearestFeatureIndex(
  features: GeoJSONFeature[],
  lat: number,
  lng: number
): number | null {
  const valid = toValidFeatures(features);
  if (valid.length === 0) return null;
  let best = valid[0];
  let bestDist = Infinity;
  for (const v of valid) {
    const d = haversineDistance(lat, lng, v.lat, v.lng);
    if (d < bestDist) {
      bestDist = d;
      best = v;
    }
  }
  return best.index;
}
