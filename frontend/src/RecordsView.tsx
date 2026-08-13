import type { JSX } from "react";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import type { RecordsResponse, Records, RoutePR } from "./api";
import { ApiError, fetchRecords } from "./api";
import type { UnitSystem } from "./format";
import { formatDistance, formatSpeed, formatElevation, formatTime } from "./format";
import { ErrorDisplay } from "./ErrorDisplay";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { PolylineMap } from "./components/PolylineMap";

// Color themes for each PR type
const PR_COLORS = {
  distance: { border: "border-violet-500/30", bg: "bg-violet-500/10", text: "text-violet-500", circle: "bg-violet-500/10" },
  time: { border: "border-blue-500/30", bg: "bg-blue-500/10", text: "text-blue-500", circle: "bg-blue-500/10" },
  speed: { border: "border-emerald-500/30", bg: "bg-emerald-500/10", text: "text-emerald-500", circle: "bg-emerald-500/10" },
  hr: { border: "border-pink-500/30", bg: "bg-pink-500/10", text: "text-pink-500", circle: "bg-pink-500/10" },
  power: { border: "border-amber-500/30", bg: "bg-amber-500/10", text: "text-amber-500", circle: "bg-amber-500/10" },
  elevation: { border: "border-gray-500/30", bg: "bg-gray-500/10", text: "text-gray-400", circle: "bg-gray-500/10" },
} as const;

type ColorTheme = keyof typeof PR_COLORS;

interface PRDef {
  key: keyof Records;
  label: string;
  format: (value: number, unitSystem: UnitSystem) => string;
  icon: JSX.Element;
  colorTheme: ColorTheme;
}

const PR_DEFS: PRDef[] = [
  { 
    key: "longest_distance_m", 
    label: "Longest Ride", 
    format: formatDistance,
    colorTheme: "distance",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    ),
  },
  { 
    key: "longest_moving_time_s", 
    label: "Longest Time", 
    format: formatTime,
    colorTheme: "time",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  { 
    key: "fastest_5000_m", 
    label: "Fastest 5km", 
    format: formatTime,
    colorTheme: "speed",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  { 
    key: "fastest_10000_m", 
    label: "Fastest 10km", 
    format: formatTime,
    colorTheme: "speed",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  { 
    key: "fastest_40000_m", 
    label: "Fastest 40km", 
    format: formatTime,
    colorTheme: "speed",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  { 
    key: "max_speed_mps", 
    label: "Max Speed", 
    format: formatSpeed,
    colorTheme: "speed",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  { 
    key: "max_hr_bpm", 
    label: "Max Heart Rate", 
    format: (v) => `${v} bpm`,
    colorTheme: "hr",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
      </svg>
    ),
  },
  { 
    key: "biggest_elevation_gain_m", 
    label: "Biggest Climb", 
    format: formatElevation,
    colorTheme: "elevation",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
      </svg>
    ),
  },
  { 
    key: "highest_sustained_power_w", 
    label: "Highest NP", 
    format: (v) => `${v} W`,
    colorTheme: "power",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
];

interface PRCardProps {
  label: string;
  value: string;
  activityId?: string;
  icon: JSX.Element;
  colorTheme: ColorTheme;
}

function PRCard({ label, value, activityId, icon, colorTheme }: PRCardProps): JSX.Element {
  const colors = PR_COLORS[colorTheme];
  
  const content = (
    <div className={`relative overflow-hidden rounded-2xl border ${colors.border} p-6 card-hover transition-all duration-300 hover:-translate-y-1 hover:shadow-xl`}>
      {/* Decorative circle */}
      <div className={`absolute top-0 right-0 w-32 h-32 ${colors.circle} rounded-full -mr-16 -mt-16`} />
      
      <div className="relative z-10">
        {/* Icon and label */}
        <div className="flex items-center gap-2 mb-3">
          <span className={colors.text}>{icon}</span>
          <span className={`text-metric-label ${colors.text}`}>{label}</span>
        </div>
        
        {/* Value */}
        <p className="text-4xl font-bold text-foreground mb-4 tabular-nums">{value}</p>
        
        {/* View activity link */}
        {activityId && (
          <div className={`pt-4 border-t ${colors.border}`}>
            <span className="flex items-center gap-2 text-primary hover:text-primary/80 text-sm font-medium transition group">
              <span>View activity</span>
              <svg className="w-4 h-4 transform group-hover:translate-x-1 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </span>
          </div>
        )}
      </div>
    </div>
  );

  if (activityId) {
    return (
      <Link to={`/activities/${activityId}`}>
        {content}
      </Link>
    );
  }

  return content;
}

function RoutePRCard({ routePR }: { routePR: RoutePR }): JSX.Element {
  const content = (
    <div className="bg-card border border-border rounded-2xl overflow-hidden card-hover transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
      <div className="flex">
        {/* Map thumbnail */}
        <div className="w-32 h-24 flex-shrink-0 bg-muted">
          {routePR.polyline ? (
            <PolylineMap 
              polyline={routePR.polyline} 
              className="w-full h-full"
              showMarkers={true}
              showMapBackground={true}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <svg className="w-8 h-8 text-muted-foreground/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 p-4 flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-foreground truncate">
              {routePR.activity_title || routePR.route_label}
            </h3>
            <p className="text-muted-foreground text-sm">Route PR</p>
          </div>
          
          <div className="text-right">
            <p className="text-metric-label mb-1">Best Time</p>
            <p className="text-2xl font-bold text-foreground tabular-nums">{formatTime(routePR.fastest_time_s)}</p>
          </div>
          
          {routePR.activity_id && (
            <div className="flex items-center text-primary">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  if (routePR.activity_id) {
    return (
      <Link to={`/activities/${routePR.activity_id}`}>
        {content}
      </Link>
    );
  }

  return content;
}

function RecordsLoadingSkeleton(): JSX.Element {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Skeleton className="h-9 w-32 mb-2" />
        <Skeleton className="h-5 w-64" />
      </div>
      
      {/* Lifetime PRs */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-6">
          <Skeleton className="w-2 h-2 rounded-full" />
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-4 w-24 ml-auto" />
        </div>
        
        <div className="grid grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="rounded-2xl border border-border p-6">
              <div className="flex items-center gap-2 mb-3">
                <Skeleton className="w-5 h-5 rounded" />
                <Skeleton className="h-3 w-20" />
              </div>
              <Skeleton className="h-10 w-24 mb-4" />
              <div className="pt-4 border-t border-border">
                <Skeleton className="h-4 w-24" />
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Route PRs */}
      <div>
        <div className="flex items-center gap-3 mb-6">
          <Skeleton className="w-2 h-2 rounded-full" />
          <Skeleton className="h-7 w-28" />
        </div>
        
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="bg-card rounded-2xl border border-border p-6">
              <div className="grid grid-cols-4 gap-6 items-center">
                <div className="col-span-2 flex items-center gap-3">
                  <Skeleton className="w-10 h-10 rounded-lg" />
                  <div>
                    <Skeleton className="h-5 w-32 mb-1" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                </div>
                <div>
                  <Skeleton className="h-3 w-16 mb-1" />
                  <Skeleton className="h-7 w-20" />
                </div>
                <div className="text-right">
                  <Skeleton className="h-4 w-24 ml-auto" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface RecordsViewProps {
  unitSystem?: UnitSystem;
}

export function RecordsView({ unitSystem = "metric" }: RecordsViewProps): JSX.Element {
  const [data, setData] = useState<RecordsResponse | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);

  useEffect(() => {
    fetchRecords()
      .then(setData)
      .catch((e) => setError(e));
  }, []);

  if (error) {
    return (
      <div className="p-8">
        <ErrorDisplay error={error} context="loading records" />
      </div>
    );
  }

  if (!data) {
    return <RecordsLoadingSkeleton />;
  }

  // Build PRs from data
  const lifetimePRs: Array<PRDef & { value: string; activityId?: string }> = [];
  for (const def of PR_DEFS) {
    const pr = data.lifetime_prs[def.key];
    if (pr) {
      lifetimePRs.push({
        ...def,
        value: def.format(pr.value, unitSystem),
        activityId: pr.activity_id,
      });
    }
  }

  const routePRs = data.route_prs;

  if (lifetimePRs.length === 0 && routePRs.length === 0) {
    return (
      <div className="p-8">
        <div className="mb-8">
          <h1 className="text-page-title mb-2">Records</h1>
          <p className="text-muted-foreground">Your personal bests and achievements</p>
        </div>
        <div className="bg-card rounded-lg border border-border">
          <EmptyState
            icon={
              <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
              </svg>
            }
            title="No personal records yet"
            description="Complete some activities to start tracking your PRs for power, distance, climbing, and more."
          />
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-page-title mb-2">Records</h1>
        <p className="text-muted-foreground">Your personal bests and achievements</p>
      </div>

      {/* Lifetime PRs */}
      {lifetimePRs.length > 0 && (
        <section className="mb-10">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-2 h-2 bg-primary rounded-full" />
            <h2 className="text-metric">Lifetime PRs</h2>
            <span className="text-muted-foreground text-sm ml-auto">
              {lifetimePRs.length} personal record{lifetimePRs.length !== 1 ? "s" : ""}
            </span>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {lifetimePRs.map((pr) => (
              <PRCard
                key={pr.key}
                label={pr.label}
                value={pr.value}
                activityId={pr.activityId}
                icon={pr.icon}
                colorTheme={pr.colorTheme}
              />
            ))}
          </div>
        </section>
      )}

      {/* Route PRs */}
      {routePRs.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-6">
            <div className="w-2 h-2 bg-success rounded-full" />
            <h2 className="text-metric">Route PRs</h2>
            <span className="text-muted-foreground text-sm ml-auto">
              {routePRs.length} route{routePRs.length !== 1 ? "s" : ""} recorded
            </span>
          </div>
          
          <div className="space-y-4">
            {routePRs.map((routePR) => (
              <RoutePRCard key={routePR.route_id} routePR={routePR} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
