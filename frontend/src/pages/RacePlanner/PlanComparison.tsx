/**
 * Plan Comparison Page
 *
 * Displays comparison between a race plan and executed activity:
 * - Header with plan/activity names, time delta, pacing score
 * - Power comparison chart (planned vs actual)
 * - Segment comparison table
 * - Insights from pacing analysis
 */

import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ComposedChart,
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
import {
  fetchRacePlan,
  fetchCourse,
  compareExecution,
  fetchMatchingActivities,
} from "@/api/race-plans";
import type {
  RacePlanDetail,
  CourseDetail,
  ExecutionComparison,
  SegmentComparison,
  MatchingActivity,
} from "@/api/types";

// =============================================================================
// Helper Functions
// =============================================================================

function formatDistance(meters: number): string {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}


function formatGrade(grade: number): string {
  const sign = grade >= 0 ? "+" : "";
  return `${sign}${grade.toFixed(1)}%`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
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

function getPacingScoreColor(score: number): string {
  if (score >= 90) return "text-success";
  if (score >= 70) return "text-warning";
  return "text-destructive";
}

// =============================================================================
// Stat Card Component
// =============================================================================

function StatCard({
  label,
  value,
  subValue,
  valueClass,
}: {
  label: string;
  value: string;
  subValue?: string;
  valueClass?: string;
}) {
  return (
    <div className="text-center">
      <div className={cn("text-metric", valueClass)}>{value}</div>
      {subValue && <div className="text-sm text-muted-foreground">{subValue}</div>}
      <div className="text-metric-label">{label}</div>
    </div>
  );
}


// =============================================================================
// Power Comparison Chart
// =============================================================================

interface ChartDataPoint {
  distance_km: number;
  planned_power_w: number;
  actual_power_w: number | null;
  grade_pct: number;
}

function buildChartData(
  segments: SegmentComparison[],
  courseSegments: { start_m: number; end_m: number }[]
): ChartDataPoint[] {
  const points: ChartDataPoint[] = [];

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const courseSeg = courseSegments[i];
    if (!courseSeg) continue;

    // Add point at segment start
    points.push({
      distance_km: courseSeg.start_m / 1000,
      planned_power_w: seg.planned_power_w,
      actual_power_w: seg.actual_power_w,
      grade_pct: seg.grade_pct,
    });

    // Add point at segment end
    points.push({
      distance_km: courseSeg.end_m / 1000,
      planned_power_w: seg.planned_power_w,
      actual_power_w: seg.actual_power_w,
      grade_pct: seg.grade_pct,
    });
  }

  return points;
}


interface PowerComparisonChartProps {
  data: ChartDataPoint[];
  className?: string;
}

function PowerComparisonChart({ data, className }: PowerComparisonChartProps) {
  if (data.length === 0) {
    return (
      <div className={cn("h-64 flex items-center justify-center bg-muted rounded-lg", className)}>
        <span className="text-muted-foreground">No comparison data available</span>
      </div>
    );
  }

  const allPowers = data.flatMap((d) => [d.planned_power_w, d.actual_power_w ?? 0]);
  const maxPower = Math.max(...allPowers);
  const minPower = Math.min(...allPowers.filter((p) => p > 0));

  return (
    <div className={cn("h-80", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
          <defs>
            <linearGradient id="deltaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(var(--chart-amber))" stopOpacity={0.2} />
              <stop offset="95%" stopColor="hsl(var(--chart-amber))" stopOpacity={0.05} />
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
            domain={[Math.max(0, minPower - 30), maxPower + 30]}
            tickFormatter={(v) => `${Math.round(v)}`}
            label={{ value: "Power (W)", angle: -90, position: "insideLeft" }}
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
                    <div>Grade: {formatGrade(point.grade_pct)}</div>
                    <div className="text-foreground">
                      Planned: <span className="font-medium">{Math.round(point.planned_power_w)} W</span>
                    </div>
                    {point.actual_power_w !== null && (
                      <div className="text-foreground">
                        Actual: <span className="font-medium">{Math.round(point.actual_power_w)} W</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            }}
          />
          {/* Planned power - dashed line */}
          <Line
            type="stepAfter"
            dataKey="planned_power_w"
            stroke="hsl(var(--muted-foreground))"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            name="Planned"
          />
          {/* Actual power - solid line */}
          <Line
            type="stepAfter"
            dataKey="actual_power_w"
            stroke="hsl(var(--chart-amber))"
            strokeWidth={2}
            dot={false}
            name="Actual"
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}


// =============================================================================
// Segment Comparison Table
// =============================================================================

interface SegmentTableProps {
  segments: SegmentComparison[];
  sortBy: "segment" | "power_delta" | "time_delta";
  onSortChange: (sort: "segment" | "power_delta" | "time_delta") => void;
}

function SegmentComparisonTable({ segments, sortBy, onSortChange }: SegmentTableProps) {
  const sortedSegments = useMemo(() => {
    const sorted = [...segments];
    switch (sortBy) {
      case "power_delta":
        return sorted.sort((a, b) => 
          Math.abs(b.power_delta_pct ?? 0) - Math.abs(a.power_delta_pct ?? 0)
        );
      case "time_delta":
        return sorted.sort((a, b) => 
          Math.abs(b.time_delta_s ?? 0) - Math.abs(a.time_delta_s ?? 0)
        );
      default:
        return sorted.sort((a, b) => a.segment_idx - b.segment_idx);
    }
  }, [segments, sortBy]);

  const getDeltaColor = (delta: number | null, inverse = false): string => {
    if (delta === null) return "";
    // For power: over = red, under = green (pushed too hard is bad)
    // For time: over = red, under = green (slower is bad)
    if (inverse) {
      return delta > 0 ? "text-destructive" : delta < 0 ? "text-success" : "";
    }
    return delta > 0 ? "text-success" : delta < 0 ? "text-destructive" : "";
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th 
              className="text-left py-2 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => onSortChange("segment")}
            >
              # {sortBy === "segment" && "↓"}
            </th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Grade</th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Planned</th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Actual</th>
            <th 
              className="text-right py-2 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => onSortChange("power_delta")}
            >
              Power Δ {sortBy === "power_delta" && "↓"}
            </th>

            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Plan Time</th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Actual Time</th>
            <th 
              className="text-right py-2 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => onSortChange("time_delta")}
            >
              Time Δ {sortBy === "time_delta" && "↓"}
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedSegments.map((seg) => (
            <tr
              key={seg.segment_idx}
              className="border-b border-border/50 hover:bg-muted/30 transition-colors"
            >
              <td className="py-2 px-3 font-medium">{seg.segment_idx + 1}</td>
              <td className="py-2 px-3 text-right">{formatGrade(seg.grade_pct)}</td>
              <td className="py-2 px-3 text-right">{Math.round(seg.planned_power_w)} W</td>
              <td className="py-2 px-3 text-right">
                {seg.actual_power_w !== null ? `${Math.round(seg.actual_power_w)} W` : "—"}
              </td>
              <td className={cn("py-2 px-3 text-right font-medium", getDeltaColor(seg.power_delta_pct, true))}>
                {seg.power_delta_pct !== null 
                  ? `${seg.power_delta_pct > 0 ? "+" : ""}${seg.power_delta_pct.toFixed(1)}%` 
                  : "—"}
              </td>
              <td className="py-2 px-3 text-right">{formatDuration(seg.planned_time_s)}</td>
              <td className="py-2 px-3 text-right">
                {seg.actual_time_s !== null ? formatDuration(seg.actual_time_s) : "—"}
              </td>
              <td className={cn("py-2 px-3 text-right font-medium", getDeltaColor(seg.time_delta_s, true))}>
                {seg.time_delta_s !== null 
                  ? `${seg.time_delta_s > 0 ? "+" : ""}${Math.round(seg.time_delta_s)}s` 
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


// =============================================================================
// Insights Card
// =============================================================================

interface InsightsCardProps {
  insights: string[];
}

function InsightsCard({ insights }: InsightsCardProps) {
  if (insights.length === 0) return null;

  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <h2 className="text-card-title mb-4">Pacing Insights</h2>
      <ul className="space-y-2">
        {insights.map((insight, idx) => {
          const isPositive = insight.toLowerCase().includes("good") || 
                            insight.toLowerCase().includes("within");
          return (
            <li key={idx} className="flex items-start gap-2 text-sm">
              <span className={cn(
                "mt-0.5 flex-shrink-0",
                isPositive ? "text-success" : "text-warning"
              )}>
                {isPositive ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                )}
              </span>
              <span>{insight}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}


// =============================================================================
// Activity Selector
// =============================================================================

interface ActivitySelectorProps {
  activities: MatchingActivity[];
  loading: boolean;
  onSelect: (activityId: string) => void;
}

function ActivitySelector({ activities, loading, onSelect }: ActivitySelectorProps) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground mb-2">No matching activities found</p>
        <p className="text-sm text-muted-foreground">
          Activities must have power data and similar distance to the course.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {activities.map((activity) => (
        <button
          key={activity.id}
          onClick={() => onSelect(activity.id)}
          className="w-full p-4 bg-card border border-border rounded-lg hover:bg-muted/50 transition text-left"
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">{activity.name || "Untitled Ride"}</div>
              <div className="text-sm text-muted-foreground">
                {formatDate(activity.started_at)} · {formatDistance(activity.total_distance_m)}
              </div>
            </div>
            <div className="text-right">
              <div className="font-medium">
                {activity.avg_power_w ? `${Math.round(activity.avg_power_w)} W` : "—"}
              </div>
              <div className="text-sm text-muted-foreground">
                {formatDuration(activity.moving_time_s)}
              </div>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}


// =============================================================================
// Main Page Component
// =============================================================================

export function PlanComparison() {
  const { planId, activityId } = useParams<{ planId: string; activityId?: string }>();
  const navigate = useNavigate();

  const [plan, setPlan] = useState<RacePlanDetail | null>(null);
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [comparison, setComparison] = useState<ExecutionComparison | null>(null);
  const [matchingActivities, setMatchingActivities] = useState<MatchingActivity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingActivities, setIsLoadingActivities] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"segment" | "power_delta" | "time_delta">("segment");

  // Load plan and course
  useEffect(() => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);

    fetchRacePlan(Number(planId))
      .then((planData) => {
        setPlan(planData);
        return fetchCourse(planData.course_id);
      })
      .then(setCourse)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [planId]);

  // Load comparison if activityId provided
  useEffect(() => {
    if (!planId || !activityId) return;

    compareExecution(Number(planId), activityId)
      .then(setComparison)
      .catch((err: Error) => setError(err.message));
  }, [planId, activityId]);


  // Load matching activities if no activityId
  useEffect(() => {
    if (!planId || activityId) return;
    setIsLoadingActivities(true);

    fetchMatchingActivities(Number(planId))
      .then(setMatchingActivities)
      .catch(() => setMatchingActivities([]))
      .finally(() => setIsLoadingActivities(false));
  }, [planId, activityId]);

  const chartData = useMemo(() => {
    if (!comparison || !course) return [];
    return buildChartData(comparison.segment_comparisons, course.segments);
  }, [comparison, course]);

  const handleActivitySelect = (selectedActivityId: string) => {
    navigate(`/race-planner/plans/${planId}/compare/${selectedActivityId}`);
  };

  if (!planId) {
    return <div className="p-6">Plan not found</div>;
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          Failed to load comparison: {error}
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


  // Show activity selector if no activityId
  if (!activityId) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <button
          onClick={() => navigate(`/race-planner/plans/${planId}`)}
          className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 hover:underline mb-6"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Plan
        </button>

        <h1 className="text-page-title mb-2">Compare Execution</h1>
        <p className="text-page-subtitle mb-6">
          Select an activity to compare against "{plan.name || course.name}"
        </p>

        <ActivitySelector
          activities={matchingActivities}
          loading={isLoadingActivities}
          onSelect={handleActivitySelect}
        />
      </div>
    );
  }

  // Show comparison if we have one
  if (!comparison) {
    return (
      <div className="p-8">
        <Skeleton className="h-6 w-32 mb-4" />
        <Skeleton className="h-24 w-full rounded-xl mb-6" />
        <Skeleton className="h-80 w-full rounded-xl" />
      </div>
    );
  }


  const isFaster = comparison.time_delta_s < 0;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate(`/race-planner/plans/${planId}`)}
          className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 hover:underline mb-4"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Plan
        </button>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-page-title">Execution Comparison</h1>
            <p className="text-page-subtitle mt-1">
              {plan.name || course.name} · {formatDistance(course.distance_m)}
            </p>
          </div>
          <div className={cn(
            "px-4 py-2 rounded-lg text-center",
            isFaster ? "bg-success/20" : "bg-destructive/20"
          )}>
            <div className={cn(
              "text-2xl font-bold tabular-nums",
              isFaster ? "text-success" : "text-destructive"
            )}>
              {comparison.time_delta_formatted}
            </div>
            <div className="text-xs text-muted-foreground">
              {isFaster ? "Faster" : "Slower"} than plan
            </div>
          </div>
        </div>
      </div>


      {/* Stats bar */}
      <div className="bg-card border border-border rounded-xl p-4 mb-8">
        <div className="grid grid-cols-5 gap-4">
          <StatCard
            label="Planned Time"
            value={comparison.total_planned_time_formatted}
          />
          <StatCard
            label="Actual Time"
            value={comparison.total_actual_time_formatted}
          />
          <StatCard
            label="Pacing Score"
            value={`${Math.round(comparison.pacing_consistency)}`}
            subValue="out of 100"
            valueClass={getPacingScoreColor(comparison.pacing_consistency)}
          />
          <StatCard
            label="Over Target"
            value={String(comparison.segments_over_target)}
            subValue="segments"
            valueClass={comparison.segments_over_target > 0 ? "text-destructive" : ""}
          />
          <StatCard
            label="Under Target"
            value={String(comparison.segments_under_target)}
            subValue="segments"
          />
        </div>
      </div>

      {/* Power Comparison Chart */}
      <div className="bg-card border border-border rounded-xl p-4 mb-8">
        <h2 className="text-card-title mb-4">Power: Planned vs Actual</h2>
        <div className="flex items-center gap-4 mb-4 text-sm">
          <div className="flex items-center gap-2">
            <svg className="w-6 h-3" viewBox="0 0 24 12">
              <line x1="0" y1="6" x2="24" y2="6" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" className="text-muted-foreground" />
            </svg>
            <span className="text-muted-foreground">Planned</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-[hsl(var(--chart-amber))]" />
            <span className="text-muted-foreground">Actual</span>
          </div>
        </div>
        <PowerComparisonChart data={chartData} />
      </div>


      {/* Segment Comparison Table */}
      <div className="bg-card border border-border rounded-xl p-4 mb-8">
        <h2 className="text-card-title mb-4">Segment Comparison</h2>
        <SegmentComparisonTable
          segments={comparison.segment_comparisons}
          sortBy={sortBy}
          onSortChange={setSortBy}
        />
      </div>

      {/* Insights */}
      <InsightsCard insights={comparison.insights} />
    </div>
  );
}
