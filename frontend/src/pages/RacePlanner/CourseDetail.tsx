/**
 * Course Detail Page
 *
 * Displays full course information:
 * - Header with name, metrics, actions
 * - Elevation profile chart with grade coloring
 * - Segments table
 * - Climbs summary card
 * - Map preview
 */

import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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
import { cn } from "@/lib/utils";
import { fetchCourse, deleteCourse } from "@/api/race-plans";
import type { CourseDetail as CourseDetailType, CourseSegment, CourseClimb } from "@/api/types";

// =============================================================================
// Helper Functions
// =============================================================================

function formatDistance(meters: number): string {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}


function formatElevation(meters: number | null): string {
  if (meters === null) return "—";
  return `${Math.round(meters)} m`;
}

function formatGrade(grade: number): string {
  return `${grade >= 0 ? "+" : ""}${grade.toFixed(1)}%`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// Grade to color mapping (matches zone colors conceptually)
function getGradeColor(grade: number): string {
  if (grade <= -4) return "hsl(var(--chart-blue))";   // steep downhill
  if (grade <= -1) return "hsl(var(--chart-emerald))"; // gentle downhill
  if (grade <= 2) return "hsl(var(--chart-gray))";    // flat
  if (grade <= 5) return "hsl(var(--chart-yellow))";  // moderate climb
  if (grade <= 8) return "hsl(var(--chart-orange))";  // steep climb
  if (grade <= 12) return "hsl(var(--chart-red))";    // very steep
  return "hsl(var(--chart-violet))";                   // extreme
}

// Climb category badge styling
function getCategoryBadge(category: string | null): { label: string; className: string } {
  switch (category) {
    case "HC":
      return { label: "HC", className: "bg-violet-500/20 text-violet-500" };
    case "1":
      return { label: "Cat 1", className: "bg-red-500/20 text-red-500" };
    case "2":
      return { label: "Cat 2", className: "bg-orange-500/20 text-orange-500" };
    case "3":
      return { label: "Cat 3", className: "bg-yellow-500/20 text-yellow-500" };
    case "4":
      return { label: "Cat 4", className: "bg-emerald-500/20 text-emerald-500" };
    default:
      return { label: "Climb", className: "bg-muted text-muted-foreground" };
  }
}


// =============================================================================
// Stat Card Component
// =============================================================================

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-metric">{value}</div>
      <div className="text-metric-label">{label}</div>
    </div>
  );
}

// =============================================================================
// Elevation Profile Chart
// =============================================================================

interface ElevationChartProps {
  profile: { distance_m: number; elevation_m: number; grade_pct: number }[];
  className?: string;
}

function ElevationChart({ profile, className }: ElevationChartProps) {
  // Resample to reasonable number of points for chart
  const chartData = useMemo(() => {
    if (profile.length === 0) return [];

    // Take every Nth point to get ~200 points max
    const step = Math.max(1, Math.floor(profile.length / 200));
    const resampled = profile.filter((_, i) => i % step === 0 || i === profile.length - 1);

    return resampled.map((p) => ({
      distance_km: p.distance_m / 1000,
      elevation_m: p.elevation_m,
      grade_pct: p.grade_pct,
    }));
  }, [profile]);

  if (chartData.length === 0) {
    return (
      <div className={cn("h-64 flex items-center justify-center bg-muted rounded-lg", className)}>
        <span className="text-muted-foreground">No elevation data</span>
      </div>
    );
  }

  const minEle = Math.min(...chartData.map((d) => d.elevation_m));
  const maxEle = Math.max(...chartData.map((d) => d.elevation_m));
  const padding = (maxEle - minEle) * 0.1 || 10;


  return (
    <div className={cn("h-64", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="elevationGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
              <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.05} />
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
            domain={[minEle - padding, maxEle + padding]}
            tickFormatter={(v) => `${Math.round(v)}`}
            label={{ value: "Elevation (m)", angle: -90, position: "insideLeft" }}
            className="text-xs"
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload || payload.length === 0) return null;
              const point = payload[0].payload;
              return (
                <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
                  <div className="font-medium mb-1">{point.distance_km.toFixed(2)} km</div>
                  <div className="space-y-0.5 text-muted-foreground">
                    <div>Elevation: <span className="text-foreground font-medium">{Math.round(point.elevation_m)} m</span></div>
                    <div>Grade: <span className="text-foreground font-medium">{formatGrade(point.grade_pct)}</span></div>
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
            fill="url(#elevationGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}


// =============================================================================
// Segments Table
// =============================================================================

interface SegmentsTableProps {
  segments: CourseSegment[];
}

function SegmentsTable({ segments }: SegmentsTableProps) {
  const [sortBy, setSortBy] = useState<"index" | "grade" | "distance">("index");

  const sortedSegments = useMemo(() => {
    const indexed = segments.map((s, i) => ({ ...s, index: i }));
    switch (sortBy) {
      case "grade":
        return [...indexed].sort((a, b) => b.avg_grade_pct - a.avg_grade_pct);
      case "distance":
        return [...indexed].sort((a, b) => b.distance_m - a.distance_m);
      default:
        return indexed;
    }
  }, [segments, sortBy]);

  if (segments.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No segments detected
      </div>
    );
  }

  return (
    <div className="overflow-x-auto max-h-80 overflow-y-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th
              className="text-left py-2 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => setSortBy("index")}
            >
              # {sortBy === "index" && "↓"}
            </th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Start</th>
            <th
              className="text-right py-2 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => setSortBy("distance")}
            >
              Length {sortBy === "distance" && "↓"}
            </th>
            <th
              className="text-right py-2 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => setSortBy("grade")}
            >
              Avg Grade {sortBy === "grade" && "↓"}
            </th>
            <th className="text-right py-2 px-3 font-medium text-muted-foreground">Gain</th>
            <th className="text-left py-2 px-3 font-medium text-muted-foreground">Type</th>
          </tr>
        </thead>
        <tbody>
          {sortedSegments.map((seg) => (
            <tr
              key={seg.index}
              className="border-b border-border/50 hover:bg-muted/30 transition-colors"
            >
              <td className="py-2 px-3 font-medium">{seg.index + 1}</td>
              <td className="py-2 px-3 text-right">{formatDistance(seg.start_m)}</td>
              <td className="py-2 px-3 text-right">{formatDistance(seg.distance_m)}</td>
              <td className="py-2 px-3 text-right">
                <span
                  className="inline-block px-2 py-0.5 rounded text-xs font-medium"
                  style={{ backgroundColor: `${getGradeColor(seg.avg_grade_pct)}20`, color: getGradeColor(seg.avg_grade_pct) }}
                >
                  {formatGrade(seg.avg_grade_pct)}
                </span>
              </td>
              <td className="py-2 px-3 text-right">{formatElevation(seg.elevation_gain_m)}</td>
              <td className="py-2 px-3 capitalize">{seg.terrain_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


// =============================================================================
// Climbs Card
// =============================================================================

interface ClimbsCardProps {
  climbs: CourseClimb[];
}

function ClimbsCard({ climbs }: ClimbsCardProps) {
  if (climbs.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-4">
        <h2 className="text-card-title mb-4">Climbs</h2>
        <div className="text-center py-4 text-muted-foreground">
          No significant climbs detected
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <h2 className="text-card-title mb-4">Climbs ({climbs.length})</h2>
      <div className="space-y-3">
        {climbs.map((climb, idx) => {
          const badge = getCategoryBadge(climb.category);
          return (
            <div
              key={idx}
              className="flex items-center justify-between p-3 bg-muted/30 rounded-lg"
            >
              <div className="flex items-center gap-3">
                <span className={cn("px-2 py-1 rounded text-xs font-medium", badge.className)}>
                  {badge.label}
                </span>
                <div>
                  <div className="font-medium">{climb.name || `Climb ${idx + 1}`}</div>
                  <div className="text-sm text-muted-foreground">
                    {formatDistance(climb.start_m)} → {formatDistance(climb.end_m)}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="font-medium">{formatDistance(climb.distance_m)}</div>
                <div className="text-sm text-muted-foreground">
                  {formatGrade(climb.avg_grade_pct)} avg · {formatElevation(climb.elevation_gain_m)} gain
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


// =============================================================================
// Course Map Preview (SVG-based, similar to upload page)
// =============================================================================

interface CourseMapProps {
  elevationProfile: { distance_m: number; elevation_m: number; grade_pct: number }[];
  className?: string;
}

function CourseMap({ elevationProfile, className }: CourseMapProps) {
  // For now, show a placeholder - full map integration would need lat/lon data
  // which isn't in the elevation_profile. This could be enhanced later.
  if (elevationProfile.length === 0) {
    return (
      <div className={cn("bg-muted rounded-lg flex items-center justify-center", className)}>
        <span className="text-muted-foreground">No route data</span>
      </div>
    );
  }

  // Show a simple elevation mini-profile as the "map"
  const width = 300;
  const height = 150;
  const padding = 10;

  const distances = elevationProfile.map((p) => p.distance_m);
  const elevations = elevationProfile.map((p) => p.elevation_m);
  const maxDist = Math.max(...distances);
  const minEle = Math.min(...elevations);
  const maxEle = Math.max(...elevations);
  const eleRange = maxEle - minEle || 1;

  // Sample points for path
  const step = Math.max(1, Math.floor(elevationProfile.length / 100));
  const points = elevationProfile
    .filter((_, i) => i % step === 0 || i === elevationProfile.length - 1)
    .map((p) => {
      const x = padding + ((p.distance_m / maxDist) * (width - 2 * padding));
      const y = height - padding - ((p.elevation_m - minEle) / eleRange) * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

  const pathD = `M ${points.join(" L ")}`;
  const areaD = `${pathD} L ${width - padding},${height - padding} L ${padding},${height - padding} Z`;


  return (
    <div className={cn("bg-muted rounded-lg overflow-hidden", className)}>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
        <defs>
          <linearGradient id="mapElevationGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
            <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.1} />
          </linearGradient>
        </defs>
        {/* Filled area */}
        <path d={areaD} fill="url(#mapElevationGradient)" />
        {/* Line */}
        <path
          d={pathD}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export function CourseDetail() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();

  const [course, setCourse] = useState<CourseDetailType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;
    setIsLoading(true);
    setError(null);

    fetchCourse(Number(courseId))
      .then(setCourse)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [courseId]);

  const handleDelete = async () => {
    if (!courseId) return;
    setIsDeleting(true);

    try {
      await deleteCourse(Number(courseId));
      navigate("/race-planner");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
      setIsDeleting(false);
    }
  };


  if (!courseId) {
    return <div className="p-6">Course not found</div>;
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg mb-4">
          Failed to load course: {error}
        </div>
        <Button variant="outline" onClick={() => navigate("/race-planner")}>
          Back to Race Planner
        </Button>
      </div>
    );
  }

  if (isLoading || !course) {
    return (
      <div className="p-8">
        <Skeleton className="h-6 w-48 mb-2" />
        <Skeleton className="h-4 w-32 mb-6" />
        <Skeleton className="h-24 w-full rounded-xl mb-6" />
        <Skeleton className="h-64 w-full rounded-xl mb-6" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate("/race-planner")}
          className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 hover:underline mb-4"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Race Planner
        </button>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-page-title">{course.name}</h1>
            <p className="text-page-subtitle mt-1">
              {course.source_type.toUpperCase()} · Uploaded {formatDate(course.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              onClick={() => navigate(`/race-planner/courses/${courseId}/generate`)}
            >
              Generate Plan
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" disabled={isDeleting}>
                  Delete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete Course</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to delete "{course.name}"? This will also delete any
                    race plans associated with this course. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleDelete}>Delete</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </div>


      {/* Stats bar */}
      <div className="bg-card border border-border rounded-xl p-4 mb-8">
        <div className="grid grid-cols-5 gap-4">
          <StatCard label="Distance" value={formatDistance(course.distance_m)} />
          <StatCard label="Elevation Gain" value={formatElevation(course.elevation_gain_m)} />
          <StatCard label="Elevation Loss" value={formatElevation(course.elevation_loss_m)} />
          <StatCard label="Min Elevation" value={formatElevation(course.min_elevation_m)} />
          <StatCard label="Max Elevation" value={formatElevation(course.max_elevation_m)} />
        </div>
      </div>

      {/* Map and Elevation Chart side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-1">
          <div className="bg-card border border-border rounded-xl p-4 h-full">
            <h2 className="text-card-title mb-4">Profile</h2>
            <CourseMap elevationProfile={course.elevation_profile} className="h-40" />
          </div>
        </div>
        <div className="lg:col-span-2">
          <div className="bg-card border border-border rounded-xl p-4">
            <h2 className="text-card-title mb-4">Elevation Profile</h2>
            <ElevationChart profile={course.elevation_profile} />
          </div>
        </div>
      </div>

      {/* Climbs and Segments */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ClimbsCard climbs={course.climbs} />
        <div className="bg-card border border-border rounded-xl p-4">
          <h2 className="text-card-title mb-4">Segments ({course.segments.length})</h2>
          <SegmentsTable segments={course.segments} />
        </div>
      </div>
    </div>
  );
}
