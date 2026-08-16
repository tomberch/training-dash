/**
 * Period Summary widget - Week/Month/Year training summary
 */
import type { JSX } from "react";
import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { Activity } from "@/api";
import { formatDuration, formatDistance, formatElevation } from "@/format";

interface PeriodSummaryProps {
  activities: Activity[];
}

interface PeriodData {
  count: number;
  duration: number;
  tss: number;
  distance: number;
  elevation: number;
}

export function PeriodSummary({ activities }: PeriodSummaryProps): JSX.Element {
  const navigate = useNavigate();
  const [summaryPeriod, setSummaryPeriod] = useState<"week" | "month" | "year">("week");

  const periodSummary = useMemo(() => {
    const now = new Date();
    let startOfCurrent: Date;
    let startOfPrevious: Date;
    let endOfPrevious: Date;

    if (summaryPeriod === "week") {
      startOfCurrent = new Date(now);
      startOfCurrent.setDate(now.getDate() - now.getDay());
      startOfCurrent.setHours(0, 0, 0, 0);
      startOfPrevious = new Date(startOfCurrent);
      startOfPrevious.setDate(startOfPrevious.getDate() - 7);
      endOfPrevious = new Date(startOfCurrent);
    } else if (summaryPeriod === "month") {
      startOfCurrent = new Date(now.getFullYear(), now.getMonth(), 1);
      startOfPrevious = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      endOfPrevious = new Date(startOfCurrent);
    } else {
      startOfCurrent = new Date(now.getFullYear(), 0, 1);
      startOfPrevious = new Date(now.getFullYear() - 1, 0, 1);
      endOfPrevious = new Date(startOfCurrent);
    }

    const currentPeriod = activities.filter(a => new Date(a.started_at) >= startOfCurrent);
    const previousPeriod = activities.filter(a => {
      const d = new Date(a.started_at);
      return d >= startOfPrevious && d < endOfPrevious;
    });



    return {
      current: {
        count: currentPeriod.length,
        duration: currentPeriod.reduce((sum, a) => sum + a.moving_time_s, 0),
        tss: currentPeriod.reduce((sum, a) => sum + (a.tss || 0), 0),
        distance: currentPeriod.reduce((sum, a) => sum + a.total_distance_m, 0),
        elevation: currentPeriod.reduce((sum, a) => sum + (a.elevation_gain_m || 0), 0),
      },
      previous: {
        count: previousPeriod.length,
        duration: previousPeriod.reduce((sum, a) => sum + a.moving_time_s, 0),
        tss: previousPeriod.reduce((sum, a) => sum + (a.tss || 0), 0),
        distance: previousPeriod.reduce((sum, a) => sum + a.total_distance_m, 0),
        elevation: previousPeriod.reduce((sum, a) => sum + (a.elevation_gain_m || 0), 0),
      },
    };
  }, [activities, summaryPeriod]);

  const isEmpty = periodSummary.current.count === 0 && periodSummary.previous.count === 0;

  return (
    <div className="bg-card rounded-xl border border-border p-6 card-hover">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-card-title">
          {summaryPeriod === "week" ? "This Week" : summaryPeriod === "month" ? "This Month" : "This Year"}
        </h2>
        <div className="flex gap-1 bg-muted rounded-lg p-0.5">
          {(["week", "month", "year"] as const).map((period) => (
            <button
              key={period}
              onClick={(e) => {
                e.stopPropagation();
                setSummaryPeriod(period);
              }}
              className={`px-2 py-1 text-xs font-medium rounded transition-fast ${
                summaryPeriod === period
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {period.charAt(0).toUpperCase() + period.slice(1)}
            </button>
          ))}
        </div>
      </div>


      {isEmpty ? (
        <PeriodSummaryEmptyState period={summaryPeriod} onNavigate={() => navigate("/activities")} />
      ) : (
        <PeriodSummaryTable current={periodSummary.current} previous={periodSummary.previous} />
      )}
    </div>
  );
}

interface PeriodSummaryEmptyStateProps {
  period: "week" | "month" | "year";
  onNavigate: () => void;
}

function PeriodSummaryEmptyState({ period, onNavigate }: PeriodSummaryEmptyStateProps): JSX.Element {
  return (
    <div className="h-48 flex flex-col items-center justify-center text-center">
      <svg className="w-16 h-16 text-muted-foreground/50 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p className="text-muted-foreground mb-1">No rides this {period} yet</p>
      <p className="text-muted-foreground/70 text-sm">Time to get out there!</p>
      <button 
        onClick={onNavigate}
        className="mt-4 text-primary hover:text-primary/80 text-sm font-medium transition-fast"
      >
        Upload a ride →
      </button>
    </div>
  );
}

interface PeriodSummaryTableProps {
  current: PeriodData;
  previous: PeriodData;
}



function PeriodSummaryTable({ current, previous }: PeriodSummaryTableProps): JSX.Element {
  const rows = [
    { label: "Rides", curr: current.count, prev: previous.count, format: (v: number) => String(v) },
    { label: "Time", curr: current.duration, prev: previous.duration, format: formatDuration },
    { label: "TSS", curr: current.tss, prev: previous.tss, format: (v: number) => String(Math.round(v)) },
    { label: "Distance", curr: current.distance, prev: previous.distance, format: formatDistance },
    { label: "Elevation", curr: current.elevation, prev: previous.elevation, format: formatElevation },
  ];

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-muted-foreground text-xs uppercase tracking-wide">
          <th className="text-left font-medium pb-3"></th>
          <th className="text-right font-medium pb-3">This</th>
          <th className="text-right font-medium pb-3">Last</th>
          <th className="text-right font-medium pb-3">Diff</th>
        </tr>
      </thead>
      <tbody className="text-foreground">
        {rows.map((row) => {
          const diff = row.curr - row.prev;
          const positive = diff >= 0;
          return (
            <tr key={row.label}>
              <td className="py-1.5 text-muted-foreground">{row.label}</td>
              <td className="py-1.5 text-right font-semibold">{row.format(row.curr)}</td>
              <td className="py-1.5 text-right text-muted-foreground">{row.format(row.prev)}</td>
              <td className={`py-1.5 text-right font-medium ${positive ? "text-success" : "text-destructive"}`}>
                {positive ? "+" : ""}{row.label === "Time" || row.label === "Distance" || row.label === "Elevation"
                  ? (positive ? "" : "-") + row.format(Math.abs(diff))
                  : diff}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
