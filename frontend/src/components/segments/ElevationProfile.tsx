/**
 * ElevationProfile - Area chart showing elevation vs distance with gradient coloring.
 *
 * Used by segment detail, suggestion cards, and segment creation preview.
 * Resamples large profiles to ≤200 points for chart performance.
 */

import { useMemo, useId } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { cn } from "@/lib/utils";
import type { ElevationPoint } from "@/api/types";

// Grade color thresholds matching the prototype's gradient profile
function getGradeColor(grade: number): string {
  const absGrade = Math.abs(grade);
  if (absGrade >= 10) return "#dc2626"; // red-600
  if (absGrade >= 8) return "#f97316"; // orange-500
  if (absGrade >= 6) return "#eab308"; // yellow-500
  if (absGrade >= 4) return "#22c55e"; // green-500
  return "#6b7280"; // gray-500
}

function formatGrade(grade: number): string {
  return `${grade >= 0 ? "+" : ""}${grade.toFixed(1)}%`;
}

export interface ElevationProfileProps {
  /** Elevation profile points from API */
  profile: ElevationPoint[];
  /** Chart height in pixels or CSS value (default: 200) */
  height?: number | string;
  /** Custom distance label formatter. Default formats as km. */
  formatDistanceLabel?: (meters: number) => string;
  /** Additional CSS classes */
  className?: string;
}

interface ChartPoint {
  distance_m: number;
  distance_km: number;
  elevation_m: number;
  grade_pct: number;
  color: string;
}

export function ElevationProfile({
  profile,
  height = 200,
  formatDistanceLabel,
  className,
}: ElevationProfileProps) {
  // Generate unique gradient ID for multiple instances on same page
  const instanceId = useId();
  const gradientId = `elevationGradient-${instanceId}`;

  // Resample to ≤200 points for chart performance
  const chartData = useMemo((): ChartPoint[] => {
    if (profile.length === 0) return [];

    // Take every Nth point to get ~200 points max
    const step = Math.max(1, Math.floor(profile.length / 200));
    const resampled = profile.filter(
      (_, i) => i % step === 0 || i === profile.length - 1
    );

    return resampled.map((p) => ({
      distance_m: p.distance_m,
      distance_km: p.distance_m / 1000,
      elevation_m: p.elevation_m,
      grade_pct: p.grade_pct,
      color: getGradeColor(p.grade_pct),
    }));
  }, [profile]);

  // Scoped override: the global `.recharts-responsive-container { min-height: 200px }`
  // rule (index.css / App.css) forces every chart to >=200px, overflowing the
  // compact slots this component is used in (suggestion cards, activity detail)
  // and covering neighbouring buttons. The consumer's `height` prop wins here.
  const heightStyle = typeof height === "number" ? `${height}px` : height;

  // Empty state
  if (chartData.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center justify-center bg-muted rounded-lg",
          className
        )}
        style={{ height: heightStyle }}
        data-testid="elevation-profile-empty"
      >
        <span className="text-muted-foreground">No elevation data</span>
      </div>
    );
  }

  // Compute Y-axis domain with padding
  const minEle = Math.min(...chartData.map((d) => d.elevation_m));
  const maxEle = Math.max(...chartData.map((d) => d.elevation_m));
  const padding = (maxEle - minEle) * 0.1 || 10;

  // Default distance formatter
  const defaultFormatDistance = (meters: number): string => {
    const km = meters / 1000;
    return km >= 1 ? `${km.toFixed(1)}` : `${(meters / 1000).toFixed(2)}`;
  };

  const distanceFormatter = formatDistanceLabel || defaultFormatDistance;

  return (
    <div
      className={cn("w-full elevation-profile", className)}
      style={{ height: heightStyle }}
      data-testid="elevation-profile"
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor="hsl(var(--primary))"
                stopOpacity={0.3}
              />
              <stop
                offset="95%"
                stopColor="hsl(var(--primary))"
                stopOpacity={0.05}
              />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="distance_m"
            tickFormatter={distanceFormatter}
            className="text-xs"
            tick={{ fill: "hsl(var(--muted-foreground))" }}
          />
          <YAxis
            domain={[minEle - padding, maxEle + padding]}
            tickFormatter={(v) => `${Math.round(v)}`}
            className="text-xs"
            tick={{ fill: "hsl(var(--muted-foreground))" }}
            width={45}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload || payload.length === 0) return null;
              const point = payload[0].payload as ChartPoint;
              return (
                <div
                  className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm"
                  data-testid="elevation-profile-tooltip"
                >
                  <div className="font-medium mb-1">
                    {point.distance_km.toFixed(2)} km
                  </div>
                  <div className="space-y-0.5 text-muted-foreground">
                    <div>
                      Elevation:{" "}
                      <span className="text-foreground font-medium">
                        {Math.round(point.elevation_m)} m
                      </span>
                    </div>
                    <div>
                      Grade:{" "}
                      <span
                        className="font-medium"
                        style={{ color: point.color }}
                      >
                        {formatGrade(point.grade_pct)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            }}
          />
          <Area
            type="monotone"
            dataKey="elevation_m"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            fill={`url(#${gradientId})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default ElevationProfile;
