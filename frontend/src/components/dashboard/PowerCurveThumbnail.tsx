/**
 * Power Curve thumbnail widget
 */
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer } from "recharts";
import type { PowerCurvePoint } from "@/api";

interface PowerCurveThumbnailProps {
  powerCurve: PowerCurvePoint[];
}

export function PowerCurveThumbnail({ powerCurve }: PowerCurveThumbnailProps): JSX.Element {
  const navigate = useNavigate();

  return (
    <div 
      className="bg-card rounded-xl border border-border p-6 cursor-pointer card-hover"
      onClick={() => navigate("/power-curve")}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-foreground">Power Curve</h2>
        <span className="text-primary hover:text-primary/80 text-sm font-medium transition-fast">View full →</span>
      </div>
      {powerCurve.length > 0 ? (
        <>
          <div className="h-40 overflow-hidden">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart 
                data={powerCurve.map(p => ({ ...p, logDuration: Math.log10(p.duration_seconds) }))}
                margin={{ top: 10, right: 15, bottom: 5, left: 5 }}
              >
                <defs>
                  <linearGradient id="powerCurveGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis 
                  dataKey="logDuration" 
                  type="number"
                  domain={[Math.log10(5), Math.log10(7200)]}
                  hide 
                />
                <YAxis 
                  domain={['dataMin - 50', 'dataMax + 50']}
                  tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                  axisLine={false}
                  tickLine={false}
                  width={35}
                />


                <Line 
                  type="monotone" 
                  dataKey="watts" 
                  stroke="var(--primary)" 
                  strokeWidth={2} 
                  dot={{ fill: "var(--primary)", r: 3 }}
                  isAnimationActive={false}
                  fill="url(#powerCurveGradient)"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <PowerCurveMetrics powerCurve={powerCurve} />
        </>
      ) : (
        <PowerCurveEmptyState />
      )}
    </div>
  );
}

function PowerCurveMetrics({ powerCurve }: { powerCurve: PowerCurvePoint[] }): JSX.Element {
  const durations = [
    { label: "5s", seconds: 5 },
    { label: "1m", seconds: 60 },
    { label: "5m", seconds: 300 },
    { label: "20m", seconds: 1200 },
  ];

  return (
    <div className="grid grid-cols-4 gap-4 mt-4">
      {durations.map(({ label, seconds }) => {
        const point = powerCurve.find(p => p.duration_seconds === seconds);
        return (
          <div key={label}>
            <p className="text-muted-foreground text-xs mb-1">{label}</p>
            <p className="text-lg font-semibold text-foreground">
              {point?.watts || "—"}
              <span className="text-sm font-normal text-muted-foreground ml-1">W</span>
            </p>
          </div>
        );
      })}
    </div>
  );
}

function PowerCurveEmptyState(): JSX.Element {
  return (
    <div className="h-40 bg-muted/30 rounded-lg flex flex-col items-center justify-center text-center relative overflow-hidden">
      <div className="absolute inset-0 opacity-10">
        <svg className="w-full h-full" viewBox="0 0 400 160" preserveAspectRatio="none">
          <defs>
            <linearGradient id="emptyPowerGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" className="text-primary" style={{ stopColor: "currentColor", stopOpacity: 0.3 }} />
              <stop offset="100%" className="text-primary" style={{ stopColor: "currentColor", stopOpacity: 0 }} />
            </linearGradient>
          </defs>
          <path d="M0 140 L50 140 L100 140 L150 140 L200 140 L250 140 L300 140 L350 100 L400 160 Z" fill="url(#emptyPowerGradient)"/>
          <path d="M0 140 L50 140 L100 140 L150 140 L200 140 L250 140 L300 140 L350 100" className="stroke-primary" strokeWidth="2" fill="none"/>
        </svg>
      </div>
      <svg className="w-16 h-16 text-muted-foreground/50 mb-3 relative z-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
      <p className="text-muted-foreground text-sm mb-1 relative z-10">No power data yet</p>
      <p className="text-muted-foreground/70 text-xs relative z-10">Upload activities with a power meter to see your curve</p>
    </div>
  );
}
