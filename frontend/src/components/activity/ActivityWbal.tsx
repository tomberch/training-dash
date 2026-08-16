import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceDot,
  ReferenceArea,
} from "recharts";
import type { WbalResponse, WbalPoint } from "../../api";
import { ChartCard } from "./ActivitySections";

interface WbalChartProps {
  wbalData: WbalResponse;
  findPositionByElapsed: (elapsed: number) => [number, number] | null;
  setHoveredPosition: (pos: [number, number] | null) => void;
}

export function WbalChart({ 
  wbalData, 
  findPositionByElapsed,
  setHoveredPosition,
}: WbalChartProps) {
  const { wbal_series, w_prime_joules, wbal_min_pct } = wbalData;
  
  if (!w_prime_joules || wbal_series.length === 0) return null;

  // Find minimum point
  const minPoint = wbal_series.reduce((min: WbalPoint, point: WbalPoint) => 
    point.wbal_pct < min.wbal_pct ? point : min
  , wbal_series[0]);

  // Color function for W'bal level
  const getWbalColor = (pct: number): string => {
    if (pct > 50) return "#22c55e"; // Green
    if (pct > 25) return "#eab308"; // Yellow
    return "#ef4444"; // Red
  };

  const formatElapsedTime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Generate nice time ticks
  const maxTime = Math.max(...wbal_series.map(d => d.elapsed_s));
  const niceIntervals = [30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600];
  const idealInterval = maxTime / 10;
  const interval = niceIntervals.find(i => i >= idealInterval) || niceIntervals[niceIntervals.length - 1];
  const ticks: number[] = [];
  for (let t = 0; t <= maxTime; t += interval) {
    ticks.push(t);
  }

  return (
    <ChartCard 
      title="W'bal" 
      subtitle={`W' = ${Math.round(w_prime_joules / 1000)} kJ • Min: ${wbal_min_pct?.toFixed(0) ?? "—"}%`}
    >
      <ResponsiveContainer width="100%" height={200}>
        <LineChart 
          data={wbal_series}
          onMouseLeave={() => setHoveredPosition(null)}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          
          {/* Color bands for depletion zones */}
          <ReferenceArea y1={0} y2={25} fill="#fee2e2" fillOpacity={0.5} />
          <ReferenceArea y1={25} y2={50} fill="#fef9c3" fillOpacity={0.5} />
          <ReferenceArea y1={50} y2={100} fill="#dcfce7" fillOpacity={0.5} />
          
          <XAxis
            dataKey="elapsed_s"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={formatElapsedTime}
            ticks={ticks}
            interval={0}
            tick={{ fontSize: 10, fill: "#6b7280" }}
            axisLine={{ stroke: "#d1d5db" }}
            tickLine={{ stroke: "#d1d5db" }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={{ stroke: "#d1d5db" }}
            tickLine={{ stroke: "#d1d5db" }}
            label={{ value: "%", angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
          />
          <RechartsTooltip
            content={({ active, payload }) => {
              if (active && payload?.[0]?.payload) {
                const p = payload[0].payload;
                const pos = findPositionByElapsed(p.elapsed_s);
                if (pos) {
                  setTimeout(() => setHoveredPosition(pos), 0);
                }
              }
              if (!active || !payload?.length) return null;
              const point = payload[0].payload;
              return (
                <div style={{
                  backgroundColor: "white",
                  border: "1px solid #e5e7eb",
                  borderRadius: "8px",
                  padding: "8px 12px",
                  fontSize: "12px",
                }}>
                  <div>W'bal: {point.wbal_pct.toFixed(0)}%</div>
                  <div style={{ color: "#6b7280" }}>
                    {(point.wbal_joules / 1000).toFixed(1)} kJ
                  </div>
                </div>
              );
            }}
          />
          
          {/* Threshold lines */}
          <ReferenceLine y={50} stroke="#22c55e" strokeDasharray="3 3" strokeOpacity={0.5} />
          <ReferenceLine y={25} stroke="#ef4444" strokeDasharray="3 3" strokeOpacity={0.5} />
          
          <Line
            type="monotone"
            dataKey="wbal_pct"
            stroke="#6366f1"
            strokeWidth={2}
            dot={false}
            name="W'bal"
          />
          
          {/* Minimum point marker */}
          <ReferenceDot
            x={minPoint.elapsed_s}
            y={minPoint.wbal_pct}
            r={6}
            fill={getWbalColor(minPoint.wbal_pct)}
            stroke="#fff"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
