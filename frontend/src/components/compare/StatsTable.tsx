import { useMemo } from "react";
import type { Activity, CompareResponse } from "../../api";
import { formatDistance, formatSpeed, formatTime, formatElevation } from "../../format";
import { formatGap } from "./compareUtils";

interface StatRow {
  label: string;
  baseValue: string | null;
  compareValue: string | null;
  baseRaw: number | null;
  compareRaw: number | null;
  delta: string | null;
  winner: "base" | "compare" | "tie" | null;
  lowerIsBetter?: boolean;
}

interface StatsTableProps {
  baseActivity: Activity;
  compareActivity: Activity;
  comparison: CompareResponse | null;
}

export function StatsTable({ baseActivity, compareActivity, comparison }: StatsTableProps) {
  const stats = useMemo((): StatRow[] => {
    const rows: StatRow[] = [];
    
    const getWinner = (base: number | null, compare: number | null, lowerIsBetter = false): "base" | "compare" | "tie" | null => {
      if (base === null || compare === null) return null;
      if (Math.abs(base - compare) < 0.01) return "tie";
      if (lowerIsBetter) return base < compare ? "base" : "compare";
      return base > compare ? "base" : "compare";
    };
    
    const formatDelta = (base: number | null, compare: number | null, formatter: (v: number) => string): string | null => {
      if (base === null || compare === null) return null;
      const diff = compare - base;
      if (Math.abs(diff) < 0.01) return "—";
      const sign = diff > 0 ? "+" : "";
      return sign + formatter(diff);
    };

    rows.push({
      label: "Moving Time", baseValue: formatTime(baseActivity.moving_time_s), compareValue: formatTime(compareActivity.moving_time_s),
      baseRaw: baseActivity.moving_time_s, compareRaw: compareActivity.moving_time_s,
      delta: formatDelta(baseActivity.moving_time_s, compareActivity.moving_time_s, (v) => formatTime(Math.abs(v))),
      winner: getWinner(baseActivity.moving_time_s, compareActivity.moving_time_s, true), lowerIsBetter: true,
    });

    rows.push({
      label: "Distance", baseValue: formatDistance(baseActivity.total_distance_m), compareValue: formatDistance(compareActivity.total_distance_m),
      baseRaw: baseActivity.total_distance_m, compareRaw: compareActivity.total_distance_m,
      delta: formatDelta(baseActivity.total_distance_m, compareActivity.total_distance_m, (v) => formatDistance(Math.abs(v))),
      winner: getWinner(baseActivity.total_distance_m, compareActivity.total_distance_m),
    });

    rows.push({
      label: "Elevation Gain", baseValue: formatElevation(baseActivity.elevation_gain_m), compareValue: formatElevation(compareActivity.elevation_gain_m),
      baseRaw: baseActivity.elevation_gain_m, compareRaw: compareActivity.elevation_gain_m,
      delta: formatDelta(baseActivity.elevation_gain_m, compareActivity.elevation_gain_m, (v) => formatElevation(Math.abs(v))),
      winner: getWinner(baseActivity.elevation_gain_m, compareActivity.elevation_gain_m),
    });

    rows.push({
      label: "Avg Speed", baseValue: formatSpeed(baseActivity.avg_speed_mps), compareValue: formatSpeed(compareActivity.avg_speed_mps),
      baseRaw: baseActivity.avg_speed_mps, compareRaw: compareActivity.avg_speed_mps,
      delta: formatDelta(baseActivity.avg_speed_mps, compareActivity.avg_speed_mps, (v) => formatSpeed(Math.abs(v))),
      winner: getWinner(baseActivity.avg_speed_mps, compareActivity.avg_speed_mps),
    });

    rows.push({
      label: "Max Speed", baseValue: formatSpeed(baseActivity.max_speed_mps), compareValue: formatSpeed(compareActivity.max_speed_mps),
      baseRaw: baseActivity.max_speed_mps, compareRaw: compareActivity.max_speed_mps,
      delta: formatDelta(baseActivity.max_speed_mps, compareActivity.max_speed_mps, (v) => formatSpeed(Math.abs(v))),
      winner: getWinner(baseActivity.max_speed_mps, compareActivity.max_speed_mps),
    });



    if (baseActivity.avg_hr_bpm !== null || compareActivity.avg_hr_bpm !== null) {
      rows.push({
        label: "Avg HR", baseValue: baseActivity.avg_hr_bpm !== null ? `${baseActivity.avg_hr_bpm} bpm` : "—",
        compareValue: compareActivity.avg_hr_bpm !== null ? `${compareActivity.avg_hr_bpm} bpm` : "—",
        baseRaw: baseActivity.avg_hr_bpm, compareRaw: compareActivity.avg_hr_bpm,
        delta: formatDelta(baseActivity.avg_hr_bpm, compareActivity.avg_hr_bpm, (v) => `${Math.abs(Math.round(v))} bpm`),
        winner: null,
      });
    }

    if (baseActivity.max_hr_bpm !== null || compareActivity.max_hr_bpm !== null) {
      rows.push({
        label: "Max HR", baseValue: baseActivity.max_hr_bpm !== null ? `${baseActivity.max_hr_bpm} bpm` : "—",
        compareValue: compareActivity.max_hr_bpm !== null ? `${compareActivity.max_hr_bpm} bpm` : "—",
        baseRaw: baseActivity.max_hr_bpm, compareRaw: compareActivity.max_hr_bpm,
        delta: formatDelta(baseActivity.max_hr_bpm, compareActivity.max_hr_bpm, (v) => `${Math.abs(Math.round(v))} bpm`),
        winner: null,
      });
    }

    if (baseActivity.avg_power_w !== null || compareActivity.avg_power_w !== null) {
      rows.push({
        label: "Avg Power", baseValue: baseActivity.avg_power_w !== null ? `${Math.round(baseActivity.avg_power_w)} W` : "—",
        compareValue: compareActivity.avg_power_w !== null ? `${Math.round(compareActivity.avg_power_w)} W` : "—",
        baseRaw: baseActivity.avg_power_w, compareRaw: compareActivity.avg_power_w,
        delta: formatDelta(baseActivity.avg_power_w, compareActivity.avg_power_w, (v) => `${Math.abs(Math.round(v))} W`),
        winner: getWinner(baseActivity.avg_power_w, compareActivity.avg_power_w),
      });
    }

    if (baseActivity.np_power_w !== null || compareActivity.np_power_w !== null) {
      rows.push({
        label: "Normalized Power", baseValue: baseActivity.np_power_w !== null ? `${Math.round(baseActivity.np_power_w)} W` : "—",
        compareValue: compareActivity.np_power_w !== null ? `${Math.round(compareActivity.np_power_w)} W` : "—",
        baseRaw: baseActivity.np_power_w, compareRaw: compareActivity.np_power_w,
        delta: formatDelta(baseActivity.np_power_w, compareActivity.np_power_w, (v) => `${Math.abs(Math.round(v))} W`),
        winner: getWinner(baseActivity.np_power_w, compareActivity.np_power_w),
      });
    }

    if (baseActivity.tss !== null || compareActivity.tss !== null) {
      rows.push({
        label: "TSS", baseValue: baseActivity.tss !== null ? `${Math.round(baseActivity.tss)}` : "—",
        compareValue: compareActivity.tss !== null ? `${Math.round(compareActivity.tss)}` : "—",
        baseRaw: baseActivity.tss, compareRaw: compareActivity.tss,
        delta: formatDelta(baseActivity.tss, compareActivity.tss, (v) => `${Math.abs(Math.round(v))}`),
        winner: getWinner(baseActivity.tss, compareActivity.tss),
      });
    }

    if (baseActivity.intensity_factor !== null || compareActivity.intensity_factor !== null) {
      rows.push({
        label: "Intensity Factor", baseValue: baseActivity.intensity_factor !== null ? baseActivity.intensity_factor.toFixed(2) : "—",
        compareValue: compareActivity.intensity_factor !== null ? compareActivity.intensity_factor.toFixed(2) : "—",
        baseRaw: baseActivity.intensity_factor, compareRaw: compareActivity.intensity_factor,
        delta: formatDelta(baseActivity.intensity_factor, compareActivity.intensity_factor, (v) => Math.abs(v).toFixed(2)),
        winner: getWinner(baseActivity.intensity_factor, compareActivity.intensity_factor),
      });
    }

    if (comparison?.gap_series && comparison.gap_series.length > 0) {
      const finalGap = comparison.gap_series[comparison.gap_series.length - 1].gap_s;
      rows.push({
        label: "Final Time Gap", baseValue: finalGap < 0 ? formatGap(Math.abs(finalGap)) + " ahead" : "—",
        compareValue: finalGap > 0 ? formatGap(finalGap) + " ahead" : "—",
        baseRaw: -finalGap, compareRaw: finalGap, delta: formatGap(finalGap),
        winner: finalGap < -0.5 ? "base" : finalGap > 0.5 ? "compare" : "tie",
      });
    }

    return rows;
  }, [baseActivity, compareActivity, comparison]);



  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-sm font-medium text-foreground">Stats Comparison</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50">
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">Metric</th>
              <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                <div className="flex items-center justify-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  {baseActivity.title || "Base"}
                </div>
              </th>
              <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                <div className="flex items-center justify-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  {compareActivity.title || "Compare"}
                </div>
              </th>
              <th className="px-4 py-2 text-center font-medium text-muted-foreground">Delta</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((stat, idx) => (
              <tr key={stat.label} className={`border-t border-border ${idx % 2 === 0 ? "" : "bg-muted/25"}`}>
                <td className="px-4 py-2 font-medium text-foreground">{stat.label}</td>
                <td className="px-4 py-2 text-center">
                  <span className={stat.winner === "base" ? "text-success font-semibold" : "text-muted-foreground"}>
                    {stat.baseValue || "—"}
                    {stat.winner === "base" && <span className="ml-1 text-success">✓</span>}
                  </span>
                </td>
                <td className="px-4 py-2 text-center">
                  <span className={stat.winner === "compare" ? "text-success font-semibold" : "text-muted-foreground"}>
                    {stat.compareValue || "—"}
                    {stat.winner === "compare" && <span className="ml-1 text-success">✓</span>}
                  </span>
                </td>
                <td className="px-4 py-2 text-center text-muted-foreground">{stat.delta || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
