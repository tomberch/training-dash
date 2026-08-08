import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { MetricEntry } from "@/components/MetricTimelineChart";

// Mock data - will be replaced with API calls
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

interface UserProfile {
  height_cm: number | null;
  gender: string | null;
}

const MOCK_CURRENT_METRICS: CurrentMetrics = {
  ftp: { id: "1", effective_date: "2026-07-01", value: 265, source: "manual" },
  ftp_previous: { id: "2", effective_date: "2026-05-10", value: 260, source: "calculated" },
  lthr: { id: "3", effective_date: "2026-06-15", value: 168, source: "calculated" },
  lthr_previous: { id: "4", effective_date: "2026-01-15", value: 165, source: "manual" },
  hrmax: { id: "5", effective_date: "2026-01-01", value: 186, source: "manual" },
  hrmax_previous: null,
  weight: { id: "6", effective_date: "2026-07-15", value: 72.5, source: "device" },
  weight_previous: { id: "7", effective_date: "2026-06-01", value: 73.0, source: "manual" },
  vo2max: { id: "8", effective_date: "2026-07-15", value: 52.3, source: "device" },
  vo2max_previous: { id: "9", effective_date: "2026-05-20", value: 51.1, source: "device" },
  resting_hr: { id: "10", effective_date: "2026-08-01", value: 52, source: "device" },
  resting_hr_previous: { id: "11", effective_date: "2026-07-15", value: 54, source: "device" },
  hrv: { id: "12", effective_date: "2026-08-01", value: 65, source: "device" },
  hrv_previous: { id: "13", effective_date: "2026-07-15", value: 62, source: "device" },
};

const MOCK_USER_PROFILE: UserProfile = {
  height_cm: 178,
  gender: "male",
};

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
                <span className="text-success">↗ +{decimals > 0 ? Math.abs(diff!).toFixed(decimals) : Math.abs(diff!)}</span>
              )}
              {trend === "down" && (
                <span className="text-destructive">↘ -{decimals > 0 ? Math.abs(diff!).toFixed(decimals) : Math.abs(diff!)}</span>
              )}
              {trend === "same" && <span>—</span>}
              {trend === null && <span>—</span>}
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

export function AthleteOverview() {
  // In a real implementation, these would come from API queries
  const [loading] = useState(false);
  const [metrics] = useState<CurrentMetrics>(MOCK_CURRENT_METRICS);
  const [userProfile] = useState<UserProfile>(MOCK_USER_PROFILE);

  const [, setSearchParams] = useSearchParams();

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
            value={userProfile.height_cm}
            unit="cm"
            onClick={() => navigateToTab("body")}
          />
          <StaticValueCard
            name="Gender"
            value={userProfile.gender}
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
