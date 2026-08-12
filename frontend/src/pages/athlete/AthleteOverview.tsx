import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { MetricEntry } from "@/components/MetricTimelineChart";
import { fetchMetrics, type MetricEntryResponse, type User } from "@/api";
import {
  BarChart3,
  Heart,
  Zap,
  Scale,
  ArrowUp,
  Users,
  Wind,
  Shield,
  Info,
  type LucideIcon,
} from "lucide-react";

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
  icon: LucideIcon;
  iconColor: string;
  ctaLabel: string;
}

function MetricSummaryCard({
  name,
  current,
  previous,
  unit,
  decimals = 0,
  onClick,
  icon: Icon,
  iconColor,
  ctaLabel,
}: MetricSummaryCardProps) {
  const { trend, diff } = calculateTrend(current, previous);

  return (
    <Card
      className={cn(
        "cursor-pointer transition-all group",
        "hover:bg-muted/50 hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      tabIndex={0}
      role="button"
    >
      <CardContent className="py-4">
        <div className="flex items-center gap-2 mb-2">
          <Icon className={cn("w-5 h-5", iconColor)} />
          <span className={cn("text-metric-label", iconColor)}>
            {name}
          </span>
        </div>
        {current ? (
          <>
            <p className="text-metric">
              {decimals > 0 ? current.value.toFixed(decimals) : current.value} {unit}
            </p>
            <p className="text-caption mt-1 flex items-center gap-1">
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
          <>
            <p className="text-xl text-muted-foreground mb-3">Not set</p>
            <Button variant="ghost" className="w-full bg-primary/10 hover:bg-primary/20 text-primary">
              {ctaLabel}
            </Button>
          </>
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
  icon: LucideIcon;
  iconColor: string;
  ctaLabel: string;
}

function StaticValueCard({
  name,
  value,
  unit,
  onClick,
  icon: Icon,
  iconColor,
  ctaLabel,
}: StaticValueCardProps) {
  const displayValue = value !== null
    ? typeof value === "string"
      ? value.charAt(0).toUpperCase() + value.slice(1)
      : `${value}${unit ? ` ${unit}` : ""}`
    : null;

  return (
    <Card
      className={cn(
        "cursor-pointer transition-all group",
        "hover:bg-muted/50 hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      tabIndex={0}
      role="button"
    >
      <CardContent className="py-4">
        <div className="flex items-center gap-2 mb-2">
          <Icon className={cn("w-5 h-5", iconColor)} />
          <span className={cn("text-metric-label", iconColor)}>
            {name}
          </span>
        </div>
        {displayValue ? (
          <p className="text-metric">{displayValue}</p>
        ) : (
          <>
            <p className="text-xl text-muted-foreground mb-3">Not set</p>
            <Button variant="ghost" className="w-full bg-primary/10 hover:bg-primary/20 text-primary">
              {ctaLabel}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// Section header
function SectionHeader({ title }: { title: string }) {
  return (
    <h2 className="text-section-heading mb-3">
      {title}
    </h2>
  );
}

// Profile completion progress bar
interface ProfileCompletionProps {
  user: User;
  metrics: CurrentMetrics;
}

interface UnlockBadge {
  icon: React.ReactNode;
  label: string;
  unlocked: boolean;
}

function ProfileCompletionBar({ user, metrics }: ProfileCompletionProps) {
  // Count filled fields (10 total)
  const fields = [
    { name: "FTP", filled: metrics.ftp !== null },
    { name: "LTHR", filled: metrics.lthr !== null },
    { name: "HRMax", filled: metrics.hrmax !== null },
    { name: "Weight", filled: metrics.weight !== null },
    { name: "Height", filled: user.height_cm !== null },
    { name: "Gender", filled: user.gender !== null },
    { name: "VO2Max", filled: metrics.vo2max !== null },
    { name: "RestingHR", filled: metrics.resting_hr !== null },
    { name: "HRV", filled: metrics.hrv !== null },
    { name: "DOB", filled: user.date_of_birth !== null },
  ];

  const filledCount = fields.filter((f) => f.filled).length;
  const totalCount = fields.length;
  const percentage = Math.round((filledCount / totalCount) * 100);

  // Unlock badges - what features become available with profile data
  const unlockBadges: UnlockBadge[] = [
    {
      icon: <BarChart3 className="w-3 h-3" />,
      label: "TSS",
      unlocked: metrics.ftp !== null,
    },
    {
      icon: <Heart className="w-3 h-3" />,
      label: "HR Zones",
      unlocked: metrics.lthr !== null || metrics.hrmax !== null,
    },
    {
      icon: <Zap className="w-3 h-3" />,
      label: "Power Zones",
      unlocked: metrics.ftp !== null,
    },
  ];

  return (
    <div className="bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/30 rounded-xl p-6 mb-8">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-card-title mb-1">Profile Completion</h3>
          <p className="text-body-secondary">
            Complete your profile to unlock all analytics features
          </p>
        </div>
        <div className="text-right">
          <p className="text-metric text-primary">{percentage}%</p>
          <p className="text-caption">
            {filledCount} of {totalCount} fields
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-3 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-primary to-primary/80 rounded-full transition-all duration-500"
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Unlock badges */}
      <div className="mt-4 flex gap-2 flex-wrap">
        {unlockBadges.map((badge) => (
          <span
            key={badge.label}
            className={cn(
              "text-xs px-3 py-1 rounded-full flex items-center gap-1.5",
              badge.unlocked
                ? "bg-success/20 text-success"
                : "bg-muted text-muted-foreground"
            )}
          >
            {badge.icon}
            {badge.unlocked ? "✓" : "Unlock"} {badge.label}
          </span>
        ))}
      </div>
    </div>
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
      {/* Profile completion progress bar */}
      <ProfileCompletionBar user={user} metrics={metrics} />

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
            icon={Zap}
            iconColor="text-primary"
            ctaLabel="Set FTP →"
          />
          <MetricSummaryCard
            name="LTHR"
            current={metrics.lthr}
            previous={metrics.lthr_previous}
            unit="bpm"
            onClick={() => navigateToTab("thresholds")}
            icon={Heart}
            iconColor="text-pink-500"
            ctaLabel="Set LTHR →"
          />
          <MetricSummaryCard
            name="HRmax"
            current={metrics.hrmax}
            previous={metrics.hrmax_previous}
            unit="bpm"
            onClick={() => navigateToTab("thresholds")}
            icon={Heart}
            iconColor="text-red-500"
            ctaLabel="Set HR Max →"
          />
        </div>
      </section>

      {/* Body section */}
      <section>
        <SectionHeader title="Body" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricSummaryCard
            name="Weight"
            current={metrics.weight ?? (user.weight_kg != null ? {
              id: "profile",
              effective_date: metrics.ftp?.effective_date ?? "1970-01-01",
              value: user.weight_kg,
              source: "manual" as const
            } : null)}
            previous={metrics.weight_previous}
            unit="kg"
            decimals={1}
            onClick={() => navigateToTab("body")}
            icon={Scale}
            iconColor="text-blue-500"
            ctaLabel="Add weight →"
          />
          <StaticValueCard
            name="Height"
            value={user.height_cm}
            unit="cm"
            onClick={() => navigateToTab("body")}
            icon={ArrowUp}
            iconColor="text-green-500"
            ctaLabel="Add height →"
          />
          <StaticValueCard
            name="Gender"
            value={user.gender}
            onClick={() => navigateToTab("body")}
            icon={Users}
            iconColor="text-purple-500"
            ctaLabel="Select →"
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
            icon={Wind}
            iconColor="text-cyan-500"
            ctaLabel="Set →"
          />
        </div>
        {/* VO2 Max info hint */}
        <div className="mt-3 p-3 rounded-lg bg-muted/50 border border-border text-sm flex items-start gap-2">
          <Info className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
          <span className="text-muted-foreground">
            VO2 Max can be estimated from your best efforts once you have more activities
          </span>
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
            icon={Heart}
            iconColor="text-green-500"
            ctaLabel="Set →"
          />
          <MetricSummaryCard
            name="HRV"
            current={metrics.hrv}
            previous={metrics.hrv_previous}
            unit="ms"
            onClick={() => navigateToTab("recovery")}
            icon={Shield}
            iconColor="text-purple-500"
            ctaLabel="Set →"
          />
        </div>
      </section>
    </div>
  );
}
