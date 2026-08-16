import { useState, useMemo } from "react";
import { ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { Activity, GeoJSONFeatureCollection } from "../../api";
import { smoothPowerData, formatDistanceKm } from "./compareUtils";

interface PowerComparisonChartProps {
  baseGeojson: GeoJSONFeatureCollection | null;
  compareGeojson: GeoJSONFeatureCollection | null;
  baseActivity: Activity;
  compareActivity: Activity;
  onHover: (state: unknown) => void;
  onLeave: () => void;
}

export function PowerComparisonChart({
  baseGeojson,
  compareGeojson,
  baseActivity,
  compareActivity,
  onHover,
  onLeave,
}: PowerComparisonChartProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  
  const chartData = useMemo(() => {
    if (!baseGeojson || !compareGeojson) return [];
    return smoothPowerData(baseGeojson.features, compareGeojson.features);
  }, [baseGeojson, compareGeojson]);
  
  const hasPowerData = useMemo(() => {
    if (!chartData.length) return false;
    return chartData.some(p => p.base_power !== null || p.compare_power !== null);
  }, [chartData]);
  
  if (!hasPowerData) {
    return (
      <div className="bg-card rounded-lg border border-border p-4">
        <h3 className="text-sm font-medium text-muted-foreground">Power Comparison</h3>
        <p className="mt-2 text-body-secondary">No power data available for these activities.</p>
      </div>
    );
  }
  
  return (
    <div className="bg-card rounded-lg border border-border">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/50 transition-fast rounded-t-lg"
      >
        <h3 className="text-sm font-medium text-foreground">Power Comparison</h3>
        <div className="flex items-center gap-4">
          {!isExpanded && (
            <div className="flex items-center gap-4 text-caption">
              <div className="flex items-center gap-1">
                <span className="w-3 h-0.5 bg-indigo-500" />
                <span>{baseActivity.title || "Base"}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-3 h-0.5 bg-amber-500" />
                <span>{compareActivity.title || "Compare"}</span>
              </div>
            </div>
          )}
          <svg
            className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      
      {isExpanded && (
        <div className="px-4 pb-4">
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} onMouseMove={onHover} onMouseLeave={onLeave} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                <XAxis dataKey="distance_m" tickFormatter={formatDistanceKm} stroke="#9ca3af" fontSize={12} />
                <YAxis stroke="#9ca3af" fontSize={12} tickFormatter={(v) => `${Math.round(v)}W`} domain={[0, "auto"]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: "0.375rem", color: "#f9fafb" }}
                  formatter={(value, name) => {
                    const v = value as number | null;
                    if (v === null) return ["No data", name];
                    if (name === "base_power") return [`${Math.round(v)} W`, baseActivity.title || "Base"];
                    if (name === "compare_power") return [`${Math.round(v)} W`, compareActivity.title || "Compare"];
                    return [v, name];
                  }}
                  labelFormatter={(label) => formatDistanceKm(label as number)}
                />
                <Line type="monotone" dataKey="base_power" stroke="#6366f1" strokeWidth={2} dot={false} connectNulls name="base_power" />
                <Line type="monotone" dataKey="compare_power" stroke="#f59e0b" strokeWidth={2} dot={false} connectNulls name="compare_power" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center justify-center gap-6 mt-3 text-caption">
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-indigo-500" />
              <span>{baseActivity.title || "Base"}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-amber-500" />
              <span>{compareActivity.title || "Compare"}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
