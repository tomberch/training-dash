/**
 * Race Plan Detail Page
 *
 * Displays a race plan with:
 * - Header with plan name, total time, comparison badge
 * - Key metrics: distance, avg power, NP, IF
 * - Interactive elevation/power chart
 * - Segment targets table
 * - Climbs summary (if any)
 */

import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { fetchRacePlan, fetchCourse, deleteRacePlan } from "@/api/race-plans";
import type {
  RacePlanDetail,
  CourseDetail,
  SegmentTarget,
  CourseSegment,
  ElevationPoint,
} from "@/api/types";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";

// =============================================================================
// Helper Functions
// =============================================================================

function formatDistance(meters: number): string {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

function formatSpeed(mps: number): string {
  const kph = mps * 3.6;
  return `${kph.toFixed(1)} km/h`;
}

function formatGrade(grade: number): string {
  const sign = grade >= 0 ? "+" : "";
  return `${sign}${grade.toFixed(1)}%`;
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function getTerrainColor(terrainType: string): string {
  switch (terrainType) {
    case "climb":
      return "text-red-600";
    case "descent":
      return "text-blue-600";
    case "flat":
    default:
      return "text-foreground";
  }
}

function getTerrainBgColor(terrainType: string): string {
  switch (terrainType) {
    case "climb":
      return "bg-red-500/10";
    case "descent":
      return "bg-blue-500/10";
    case "flat":
    default:
      return "bg-muted/50";
  }
}

// =============================================================================
// Chart Data Preparation
// =============================================================================

interface ChartDataPoint {
  distance_km: number;
  elevation_m: number;
  power_w: number | null;
  grade_pct: number;
}

function buildChartData(
  elevationProfile: ElevationPoint[],
  segments: CourseSegment[],
  targets: SegmentTarget[]
): ChartDataPoint[] {
  // Build a map of segment_idx -> target power
  const targetMap = new Map<number, number>();
  for (const t of targets) {
    targetMap.set(t.segment_idx, t.power_w);
  }

  // Build segment lookup by distance
  const segmentAtDistance = (distance_m: number): number => {
    for (let i = 0; i < segments.length; i++) {
      if (distance_m >= segments[i].start_m && distance_m < segments[i].end_m) {
        return i;
      }
    }
    return segments.length - 1;
  };

  return elevationProfile.map((point) => ({
    distance_km: point.distance_m / 1000,
    elevation_m: point.elevation_m,
    power_w: targetMap.get(segmentAtDistance(point.distance_m)) ?? null,
    grade_pct: point.grade_pct,
  }));
}

// =============================================================================
// Stat Card Component
// =============================================================================

function StatCard({
  label,
  value,
  unit,
}: {
  label: string;
  value: string | number;
  unit?: string;
}) {
  return (
    <div className="text-center">
      <div className="text-metric">
        {value}
        {unit && <span className="text-lg ml-0.5">{unit}</span>}
      </div>
      <div className="text-metric-label">{label}</div>
    </div>
  );
}

// =============================================================================
// Elevation/Power Chart Component
// =============================================================================

interface ElevationPowerChartProps {
  data: ChartDataPoint[];
  className?: string;
}

function ElevationPowerChart({ data, className }: ElevationPowerChartProps) {
  if (data.length === 0) {
    return (
      <div className={cn("h-64 flex items-center justify-center bg-muted rounded-lg", className)}>
        <span className="text-muted-foreground">No elevation data available</span>
      </div>
    );
  }

  const maxElevation = Math.max(...data.map((d) => d.elevation_m));
  const minElevation = Math.min(...data.map((d) => d.elevation_m));
  const elevPadding = (maxElevation - minElevation) * 0.1 || 50;

  const powerValues = data.filter((d) => d.power_w !== null).map((d) => d.power_w!);
  const maxPower = powerValues.length > 0 ? Math.max(...powerValues) : 300;
  const minPower = powerValues.length > 0 ? Math.min(...powerValues) : 100;

  return (
    <div className={cn("h-80", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 60, left: 10, bottom: 0 }}>
          <defs>
            <linearGradient id="elevationGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(var(--chart-emerald))" stopOpacity={0.4} />
              <stop offset="95%" stopColor="hsl(var(--chart-emerald))" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="distance_km"
            tickFormatter={(v) => `${v.toFixed(0)}`}
            label={{ value: "Distance (km)", position: "bottom", offset: -5 }}
            className="text-xs"
          />
          <YAxis
            yAxisId="elevation"
            orientation="left"
            domain={[minElevation - elevPadding, maxElevation + elevPadding]}
            tickFormatter={(v) => `${Math.round(v)}`}
            label={{ value: "Elevation (m)", angle: -90, position: "insideLeft" }}
            className="text-xs"
          />
          <YAxis
            yAxisId="power"
            orientation="right"
            domain={[Math.max(0, minPower - 50), maxPower + 50]}
            tickFormatter={(v) => `${Math.round(v)}`}
            label={{ value: "Power (W)", angle: 90, position: "insideRight" }}
            className="text-xs"
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload || payload.length === 0) return null;
              const point = payload[0].payload as ChartDataPoint;
              return (
                <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
                  <div className="font-medium mb-1">{point.distance_km.toFixed(2)} km</div>
                  <div className="space-y-0.5 text-muted-foreground">
                    <div>Elevation: {Math.round(point.elevation_m)} m</div>
                    <div>Grade: {formatGrade(point.grade_pct)}</div>
                    {point.power_w !== null && <div>Power: {Math.round(point.power_w)} W</div>}
                  </div>
                </div>
              );
            }}
          />
          <Area
            yAxisId="elevation"
            type="monotone"
            dataKey="elevation_m"
            stroke="hsl(var(--chart-emerald))"
            fill="url(#elevationGradient)"
            strokeWidth={2}
          />
          <Line
            yAxisId="power"
            type="stepAfter"
            dataKey="power_w"
            stroke="hsl(var(--chart-amber))"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// =============================================================================
// Segment Table Component
// =============================================================================

interface SegmentTableProps {
  segments: CourseSegment[];
  targets: SegmentTarget[];
}

function SegmentTable({ segments, targets }: SegmentTableProps) {
  // Build target map
  const targetMap = new Map<number, SegmentTarget>();
  for (const t of targets) {
    targetMap.set(t.segment_idx, t);
  }

  if (segments.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">No segment data available</div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left py-2 px-3 font-medium text-muted-foreground">#</th>
            <th className="text-left py-2 px-3 font-medium text-muted-foreground">Distance</th>
            <th className="text-left py-2 px-3 font-medium text-muted-foreground">Length</th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Grade</th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Power</th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Speed</th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Time</th>
          </tr>
        </thead>
        <tbody>
          {segments.map((seg, idx) => {
            const target = targetMap.get(idx);
            return (
              <tr
                key={idx}
                className={cn(
                  "border-b border-border/50 hover:bg-muted/30 transition-colors",
                  getTerrainBgColor(seg.terrain_type)
                )}
              >
                <td className="py-2 px-3 font-medium">{idx + 1}</td>
                <td className="py-2 px-3">{formatDistance(seg.start_m)}</td>
                <td className="py-2 px-3">{formatDistance(seg.distance_m)}</td>
                <td className={cn("py-2 px-3 text-right font-medium", getTerrainColor(seg.terrain_type))}>
                  {formatGrade(seg.avg_grade_pct)}
                </td>
                <td className="py-2 px-3 text-right font-medium">
                  {target ? `${Math.round(target.power_w)} W` : "—"}
                </td>
                <td className="py-2 px-3 text-right">
                  {target ? formatSpeed(target.speed_mps) : "—"}
                </td>
                <td className="py-2 px-3 text-right">
                  {target ? formatDuration(target.time_s) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export function PlanDetail() {
  const { planId } = useParams<{ planId: string }>();
  const navigate = useNavigate();

  const [plan, setPlan] = useState<RacePlanDetail | null>(null);
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);

    fetchRacePlan(Number(planId))
      .then((planData) => {
        setPlan(planData);
        // Fetch course details
        return fetchCourse(planData.course_id);
      })
      .then(setCourse)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [planId]);

  const chartData = useMemo(() => {
    if (!plan || !course) return [];
    return buildChartData(course.elevation_profile, course.segments, plan.segment_targets);
  }, [plan, course]);

  const handleDelete = async () => {
    if (!planId) return;
    setIsDeleting(true);
    try {
      await deleteRacePlan(Number(planId));
      toast.success("Race plan deleted");
      navigate("/race-planner");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete race plan");
    } finally {
      setIsDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  if (!planId) {
    return <div className="p-6">Plan not found</div>;
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          Failed to load race plan: {error}
        </div>
        <Button variant="outline" className="mt-4" onClick={() => navigate("/race-planner")}>
          Back to Race Planner
        </Button>
      </div>
    );
  }

  if (isLoading || !plan || !course) {
    return (
      <div className="p-8">
        <Skeleton className="h-6 w-32 mb-4" />
        <Skeleton className="h-24 w-full rounded-xl mb-6" />
        <Skeleton className="h-80 w-full rounded-xl mb-6" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  // Calculate improvement text
  let improvementText = "";
  if (plan.comparison.improvement_vs_constant_pct) {
    improvementText = `${plan.comparison.improvement_vs_constant_pct.toFixed(1)}% faster than constant power`;
  } else if (plan.comparison.improvement_vs_heuristic_pct) {
    improvementText = `${plan.comparison.improvement_vs_heuristic_pct.toFixed(1)}% faster than heuristic`;
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={() => navigate("/race-planner")}
            className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 hover:underline"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Race Planner
          </button>

          <div className="flex items-center gap-2">
            <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
              <AlertDialogTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                  title="Delete"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete Race Plan</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to delete this race plan? This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDelete}
                    disabled={isDeleting}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {isDeleting ? "Deleting..." : "Delete"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>

        {/* Title and improvement badge */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-page-title">{plan.name || course.name}</h1>
            <p className="text-page-subtitle mt-1">
              {course.name} · {formatDistance(course.distance_m)}
            </p>
          </div>
          {improvementText && (
            <span className="px-3 py-1.5 bg-success/20 text-success text-sm font-medium rounded-full">
              {improvementText}
            </span>
          )}
        </div>
      </div>

      {/* Stats bar */}
      <div className="bg-card border border-border rounded-xl p-4 mb-8">
        <div className="grid grid-cols-5 gap-4">
          <StatCard label="Total Time" value={plan.total_time_formatted} />
          <StatCard label="Distance" value={formatDistance(course.distance_m)} />
          <StatCard label="Avg Power" value={Math.round(plan.avg_power_w)} unit="W" />
          <StatCard
            label="Normalized Power"
            value={plan.normalized_power_w ? Math.round(plan.normalized_power_w) : "—"}
            unit={plan.normalized_power_w ? "W" : undefined}
          />
          <StatCard
            label="IF"
            value={plan.intensity_factor ? plan.intensity_factor.toFixed(2) : "—"}
          />
        </div>
      </div>

      {/* Warnings */}
      {plan.warnings.length > 0 && (
        <div className="bg-warning/10 border border-warning/20 rounded-lg p-4 mb-8">
          <h3 className="font-medium text-warning mb-2">Warnings</h3>
          <ul className="list-disc list-inside text-sm text-warning/80 space-y-1">
            {plan.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Elevation/Power Chart */}
      <div className="bg-card border border-border rounded-xl p-4 mb-8">
        <h2 className="text-card-title mb-4">Elevation & Power Profile</h2>
        <ElevationPowerChart data={chartData} />
      </div>

      {/* Segment Table */}
      <div className="bg-card border border-border rounded-xl p-4 mb-8">
        <h2 className="text-card-title mb-4">Segment Targets</h2>
        <SegmentTable segments={course.segments} targets={plan.segment_targets} />
      </div>

      {/* Rider & Bike Parameters */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <h2 className="text-card-title mb-4">Rider Parameters</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Weight</dt>
              <dd className="font-medium">{plan.rider_params.weight_kg} kg</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">FTP</dt>
              <dd className="font-medium">{plan.rider_params.ftp_watts} W</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">CP</dt>
              <dd className="font-medium">
                {plan.rider_params.cp_watts ? `${plan.rider_params.cp_watts} W` : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">W'</dt>
              <dd className="font-medium">
                {plan.rider_params.w_prime_joules
                  ? `${(plan.rider_params.w_prime_joules / 1000).toFixed(1)} kJ`
                  : "—"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="bg-card border border-border rounded-xl p-4">
          <h2 className="text-card-title mb-4">Bike Parameters</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Weight</dt>
              <dd className="font-medium">
                {plan.bike_params.weight_kg ? `${plan.bike_params.weight_kg} kg` : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">CdA</dt>
              <dd className="font-medium">{plan.bike_params.cda.toFixed(3)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Crr</dt>
              <dd className="font-medium">{plan.bike_params.crr.toFixed(4)}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* W'bal prediction */}
      {plan.wbal_prediction && plan.wbal_prediction.min_wbal !== null && (
        <div className="bg-card border border-border rounded-xl p-4 mt-4">
          <h2 className="text-card-title mb-4">W'bal Prediction</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Minimum W'bal</dt>
              <dd className="font-medium">
                {(plan.wbal_prediction.min_wbal / 1000).toFixed(1)} kJ
              </dd>
            </div>
            {plan.wbal_prediction.min_wbal_distance_m !== null && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">At Distance</dt>
                <dd className="font-medium">
                  {formatDistance(plan.wbal_prediction.min_wbal_distance_m)}
                </dd>
              </div>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}
