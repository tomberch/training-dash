import type { GeoJSONFeatureCollection, GapPoint } from "../../api";

export function gapColor(gap: number): string {
  if (gap < -0.5) return "#10b981"; // green = faster (negative gap means ahead)
  if (gap > 0.5) return "#ef4444"; // red = slower (positive gap means behind)
  return "#6366f1"; // neutral indigo
}

export function formatDistanceKm(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`;
}

export function formatGap(seconds: number): string {
  const abs = Math.abs(seconds);
  const sign = seconds >= 0 ? "+" : "-";
  if (abs < 60) return `${sign}${abs.toFixed(0)}s`;
  const mins = Math.floor(abs / 60);
  const secs = Math.floor(abs % 60);
  return `${sign}${mins}:${secs.toString().padStart(2, "0")}`;
}

export interface GapChartPoint {
  distance_m: number;
  gap_s: number;
  elevation_m: number | null;
}

export interface PowerChartPoint {
  distance_m: number;
  base_power: number | null;
  compare_power: number | null;
}

export function smoothPowerData(
  baseFeatures: GeoJSONFeatureCollection["features"],
  compareFeatures: GeoJSONFeatureCollection["features"],
  windowMeters: number = 100
): PowerChartPoint[] {
  const baseByDist = new Map<number, number | null>();
  const compareByDist = new Map<number, number | null>();
  
  for (const f of baseFeatures) {
    baseByDist.set(f.properties.distance_m, f.properties.power_w);
  }
  for (const f of compareFeatures) {
    compareByDist.set(f.properties.distance_m, f.properties.power_w);
  }
  
  const allDistances = Array.from(
    new Set([...baseByDist.keys(), ...compareByDist.keys()])
  ).sort((a, b) => a - b);
  
  const sampledDistances: number[] = [];
  const maxDist = Math.max(...allDistances);
  for (let d = 0; d <= maxDist; d += 50) {
    sampledDistances.push(d);
  }
  
  const result: PowerChartPoint[] = [];
  
  for (const dist of sampledDistances) {
    const windowStart = dist - windowMeters / 2;
    const windowEnd = dist + windowMeters / 2;
    
    let baseSum = 0, baseCount = 0;
    for (const [d, p] of baseByDist) {
      if (d >= windowStart && d <= windowEnd && p !== null) {
        baseSum += p;
        baseCount++;
      }
    }
    
    let compareSum = 0, compareCount = 0;
    for (const [d, p] of compareByDist) {
      if (d >= windowStart && d <= windowEnd && p !== null) {
        compareSum += p;
        compareCount++;
      }
    }
    
    result.push({
      distance_m: dist,
      base_power: baseCount > 0 ? baseSum / baseCount : null,
      compare_power: compareCount > 0 ? compareSum / compareCount : null,
    });
  }
  
  return result;
}

export function smoothGapData(
  gapSeries: GapPoint[],
  elevationByDistance: Map<number, number>
): GapChartPoint[] {
  const windowMeters = 100;
  
  return gapSeries.map((point) => {
    const windowStart = point.distance_m - windowMeters / 2;
    const windowEnd = point.distance_m + windowMeters / 2;
    
    const windowPoints = gapSeries.filter(
      (p) => p.distance_m >= windowStart && p.distance_m <= windowEnd
    );
    
    const avgGap = windowPoints.reduce((sum, p) => sum + p.gap_s, 0) / windowPoints.length;
    
    let nearestElev: number | null = null;
    let minDist = Infinity;
    for (const [dist, elev] of elevationByDistance) {
      const d = Math.abs(dist - point.distance_m);
      if (d < minDist) {
        minDist = d;
        nearestElev = elev;
      }
    }
    
    return {
      distance_m: point.distance_m,
      gap_s: avgGap,
      elevation_m: nearestElev,
    };
  });
}
