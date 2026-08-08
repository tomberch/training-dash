import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { MetricEntry } from "@/components/MetricTimelineChart";
import { fetchMetrics, type MetricEntryResponse, type User } from "@/api";

// Convert API response to MetricEntry
function toMetricEntry(resp: MetricEntryResponse): MetricEntry {
  return {
    id: String(resp.id),
    effective_date: resp.effective_date,
    value: resp.value,
    source: resp.source,
    source_detail: resp.source_detail ?? undefined,
    notes: resp.notes ?? undefined,
  };
}

// Metrics we display in the overview
interface CurrentMetrics {
  ftp: MetricEntry | null;
  ftp_previous: MetricEntry | null;
  lthr: MetricEntry | null;
  lthr_previous: MetricEntry | null;
  hrmax: MetricEntry | null;
  hrmax_previous: MetricEntry | null;
  weight: MetricEntry | null;
  weight_previous: MetricEntry | null;
  vo2max: MetricEntry | null;
  vo2max_previous: MetricEntry | null;
  resting_hr: MetricEntry | null;
  resting_hr_previous: MetricEntry | null;
  hrv: MetricEntry | null;
  hrv_previous: MetricEntry | null;
}

// Format date for display
function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Trend calculation
type Trend = "up" | "down" | "same" | null;

function calculateTrend(current: MetricEntry | null, previous: MetricEntry | null): { trend: Trend; diff: number | null } {
  if (!current || !previous) {
    return { trend: null, diff: null };
  }
  const diff = current.value - previous.value;
  if (diff > 0) return { trend: "up", diff };
  if (diff < 0) return { trend: "down", diff };
  return { trend: "same", diff: 0 };
}

// Metric summary card with trend indicator
interface MetricSummaryCardProps {
  name: string;
  current: MetricEntry | null;
  previous: MetricEntry | null;
  unit: string;
  decimals?: number;
  onClick: () => void;
}

function MetricSummaryCard({ name, current, previous, unit, decimals = 0, onClick }: MetricSummaryCardProps) {
  const { trend, diff } = calculateTrend(current, previous);

  return (
    <Card
      className={cn(
        "cursor-pointer transition-colors",
        "hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      tabIndex={0}
      role="button"
    >
      <CardContent className="py-4">
        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
          {name}
        </p>
        {current ? (
          <>
            <p className="text-2xl font-bold text-foreground">
              {decimals > 0 ? current.value.toFixed(decimals) : current.value} {unit}
            </p>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              {trend === "up" && (
                <span className="text-success">+{decimals > 0 ? Math.abs(diff!).toFixed(decimals) : Math.abs(diff!)}</span>
              )}
              {trend === "down" && (
                <span className="text-destructive">-{decimals > 0 ? Math.abs(diff!).toFixed(decimals) : Math.abs(diff!)}</span>
              )}
              {trend === "same" && <span></span>}
              {trend === null && <span></span>}
              <span>{formatDate(current.effective_date)}</span>
            </p>
          </>
        ) : (
          <p className="text-xl text-muted-foreground">Not set</p>
        )}
      </CardContent>
    </Card>
  );
}

// Static value card for non-historical data (height, gender)
interface StaticValueCardProps {
  name: string;
  value: string | number | null;
  unit?: string;
  onClick: () => void;
}

function StaticValueCard({ name, value, unit, onClick }: StaticValueCardProps) {
  const displayValue = value !== null
    ? typeof value === "string"
      ? value.charAt(0).toUpperCase() + value.slice(1)
      : `${value}${unit ? ` ${unit}` : ""}`
    : null;

  return (
    <Card
      className={cn(
        "cursor-pointer transition-colors",
        "hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      tabIndex={0}
      role="button"
    >
      <CardContent className="py-4">
        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
          {name}
        </p>
        {displayValue ? (
          <p className="text-2xl font-bold text-foreground">{displayValue}</p>
        ) : (
          <p className="text-xl text-muted-foreground">Not set</p>
        )}
      </CardContent>
    </Card>
  );
}

// Section header
function SectionHeader({ title }: { title: string }) {
  return (
    <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
      {title}
    </h2>
  );
}

// Loading skeleton
function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {[1, 2, 3, 4].map((section) => (
        <section key={section}>
          <Skeleton className="h-4 w-24 mb-3" />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[1, 2, 3].map((card) => (
              <Card key={card}>
                <CardContent className="py-4">
                  <Skeleton className="h-3 w-12 mb-2" />
                  <Skeleton className="h-8 w-20 mb-1" />
                  <Skeleton className="h-3 w-16" />
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// Helper to get current and previous from sorted entries
function getCurrentAndPrevious(entries: MetricEntryResponse[]): { current: MetricEntry | null; previous: MetricEntry | null } {
  if (entries.length === 0) {
    return { current: null, previous: null };
  }
  // Entries come sorted descending by date
  const current = toMetricEntry(entries[0]);
  const previous = entries.length > 1 ? toMetricEntry(entries[1]) : null;
  return { current, previous };
}

interface AthleteOverviewProps {
  user: User;
}

export function AthleteOverview({ user }: AthleteOverviewProps) {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<CurrentMetrics>({
    ftp: null, ftp_previous: null,
    lthr: null, lthr_previous: null,
    hrmax: null, hrmax_previous: null,
    weight: null, weight_previous: null,
    vo2max: null, vo2max_previous: null,
    resting_hr: null, resting_hr_previous: null,
    hrv: null, hrv_previous: null,
  });

  const [, setSearchParams] = useSearchParams();

  // Fetch all metrics and organize by type
  const loadMetrics = useCallback(async () => {
    try {
      const data = await fetchMetrics({ limit: 500 });
      
      // Group by metric type (API returns sorted by date desc)
      const grouped: Record<string, MetricEntryResponse[]> = {};
      for (const entry of data) {
        if (!grouped[entry.metric_type]) {
          grouped[entry.metric_type] = [];
        }
        grouped[entry.metric_type].push(entry);
      }
      
      // Extract current and previous for each metric
      const ftp = getCurrentAndPrevious(grouped["ftp"] || []);
      const lthr = getCurrentAndPrevious(grouped["lthr"] || []);
      const hrmax = getCurrentAndPrevious(grouped["hrmax"] || []);
      const weight = getCurrentAndPrevious(grouped["weight_kg"] || []);
      const vo2max = getCurrentAndPrevious(grouped["vo2max"] || []);
      const restingHr = getCurrentAndPrevious(grouped["resting_hr"] || []);
      const hrv = getCurrentAndPrevious(grouped["hrv"] || []);
      
      setMetrics({
        ftp: ftp.current, ftp_previous: ftp.previous,
        lthr: lthr.current, lthr_previous: lthr.previous,
        hrmax: hrmax.current, hrmax_previous: hrmax.previous,
        weight: weight.current, weight_previous: weight.previous,
        vo2max: vo2max.current, vo2max_previous: vo2max.previous,
        resting_hr: restingHr.current, resting_hr_previous: restingHr.previous,
        hrv: hrv.current, hrv_previous: hrv.previous,
      });
    } catch (err) {
      console.error("Failed to load metrics:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  // Navigate to a specific tab
  function navigateToTab(tab: string) {
    setSearchParams({ tab });
  }

  if (loading) {
    return <LoadingSkeleton />;
  }

  return (
    <div className="space-y-8">
      {/* Thresholds section */}
      <section>
        <SectionHeader title="Thresholds" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricSummaryCard
            name="FTP"
            current={metrics.ftp}
            previous={metrics.ftp_previous}
            unit="W"
            onClick={() => navigateToTab("thresholds")}
          />
          <MetricSummaryCard
            name="LTHR"
            current={metrics.lthr}
            previous={metrics.lthr_previous}
            unit="bpm"
            onClick={() => navigateToTab("thresholds")}
          />
          <MetricSummaryCard
            name="HRmax"
            current={metrics.hrmax}
            previous={metrics.hrmax_previous}
            unit="bpm"
            onClick={() => navigateToTab("thresholds")}
          />
        </div>
      </section>

      {/* Body section */}
      <section>
        <SectionHeader title="Body" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricSummaryCard
            name="Weight"
            current={metrics.weight}
            previous={metrics.weight_previous}
            unit="kg"
            decimals={1}
            onClick={() => navigateToTab("body")}
          />
          <StaticValueCard
            name="Height"
            value={user.height_cm}
            unit="cm"
            onClick={() => navigateToTab("body")}
          />
          <StaticValueCard
            name="Gender"
            value={user.gender}
            onClick={() => navigateToTab("body")}
          />
        </div>
      </section>

      {/* Fitness section */}
      <section>
        <SectionHeader title="Fitness" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricSummaryCard
            name="VO2 Max"
            current={metrics.vo2max}
            previous={metrics.vo2max_previous}
            unit="ml/kg/min"
            decimals={1}
            onClick={() => navigateToTab("fitness")}
          />
        </div>
      </section>

      {/* Recovery section */}
      <section>
        <SectionHeader title="Recovery" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <MetricSummaryCard
            name="Resting HR"
            current={metrics.resting_hr}
            previous={metrics.resting_hr_previous}
            unit="bpm"
            onClick={() => navigateToTab("recovery")}
          />
          <MetricSummaryCard
            name="HRV"
            current={metrics.hrv}
            previous={metrics.hrv_previous}
            unit="ms"
            onClick={() => navigateToTab("recovery")}
          />
        </div>
      </section>
    </div>
  );
}
