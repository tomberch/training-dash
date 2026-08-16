/**
 * PMC Sparkline widget - Performance Management Chart thumbnail
 */
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import type { PMCPoint } from "@/api";
import { TSB_ZONES, getTSBZone } from "@/constants";

interface PMCSparklineProps {
  pmcData: PMCPoint[];
  currentPMC: PMCPoint | null;
  ctlTrend: number | null;
}

export function PMCSparkline({ pmcData, currentPMC, ctlTrend }: PMCSparklineProps): JSX.Element {
  const navigate = useNavigate();
  const currentZone = currentPMC ? getTSBZone(currentPMC.tsb) : null;

  return (
    <div 
      className="lg:col-span-2 bg-card rounded-xl border border-border p-6 cursor-pointer card-hover flex flex-col"
      onClick={() => navigate("/pmc")}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-card-title">Performance Management</h2>
        {currentZone && (
          <span
            className="px-3 py-1 text-sm font-semibold rounded-full text-gray-800"
            style={{ backgroundColor: currentZone.color }}
          >
            {currentZone.name}
          </span>
        )}
      </div>
      
      {pmcData.length > 0 ? (
        <>
          <div className="flex gap-4 flex-1 min-h-0">
            {/* Stacked metrics on the left */}
            <div className="flex flex-col justify-center gap-3 pr-4 border-r border-border">
              <div>
                <span className="text-muted-foreground text-xs uppercase tracking-wide">CTL</span>
                <p className="text-xl font-bold text-chart-ctl">
                  {currentPMC?.ctl.toFixed(0) ?? 0}
                  {ctlTrend !== null && (
                    <span className={`ml-1 text-sm font-medium ${ctlTrend > 0 ? "text-success" : ctlTrend < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                      {ctlTrend > 0 ? "↑" : ctlTrend < 0 ? "↓" : "→"}{Math.abs(ctlTrend).toFixed(0)}%
                    </span>
                  )}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground text-xs uppercase tracking-wide">ATL</span>
                <p className="text-xl font-bold text-chart-atl">{currentPMC?.atl.toFixed(0) ?? 0}</p>
              </div>
              <div>
                <span className="text-muted-foreground text-xs uppercase tracking-wide">TSB</span>
                <p className="text-xl font-bold text-chart-tsb">{currentPMC?.tsb.toFixed(0) ?? 0}</p>
              </div>
            </div>
            
            {/* Chart taking remaining space */}
            <div className="flex-1 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={pmcData} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#9ca3af" strokeOpacity={0.3} vertical={false} />
                  {TSB_ZONES.map((zone) => (
                    <ReferenceArea
                      key={zone.name}
                      y1={zone.min}
                      y2={zone.max}
                      fill={zone.color}
                      fillOpacity={0.12}
                      ifOverflow="hidden"
                    />
                  ))}
                  <XAxis dataKey="date" hide />
                  <YAxis domain={["auto", "auto"]} hide />
                  <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" strokeOpacity={0.6} />
                  {/* Weekly markers - every Monday */}
                  {pmcData
                    .filter(p => new Date(p.date).getDay() === 1)
                    .map(p => (
                      <ReferenceLine
                        key={`week-${p.date}`}
                        x={p.date}
                        stroke="#9ca3af"
                        strokeOpacity={0.4}
                        strokeDasharray="2 4"
                      />
                    ))}
                  <ReferenceLine
                    x={new Date().toISOString().split("T")[0]}
                    stroke="var(--color-success)"
                    strokeWidth={2}
                  />
                  <Line type="monotone" dataKey="ctl" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="atl" stroke="#ec4899" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="tsb" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          
          {/* Zone legend */}
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 justify-center">
            {TSB_ZONES.map((zone) => (
              <div key={zone.name} className="flex items-center gap-1.5">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: zone.color }}
                />
                <span className="text-xs text-muted-foreground">{zone.name}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <PMCEmptyState />
      )}
    </div>
  );
}

function PMCEmptyState(): JSX.Element {
  return (
    <div className="h-48 bg-muted/30 rounded-lg mb-4 flex flex-col items-center justify-center text-center relative overflow-hidden">
      {/* Decorative gradient wave */}
      <div className="absolute inset-0 opacity-10">
        <svg className="w-full h-full" viewBox="0 0 400 200" preserveAspectRatio="none">
          <path d="M0 150 Q50 140 100 160 T200 140 T300 120 T400 100" stroke="currentColor" className="text-primary" fill="none" strokeWidth="2"/>
          <path d="M0 150 Q50 140 100 160 T200 140 T300 120 T400 100 V200 H0 Z" className="fill-primary" opacity="0.3"/>
        </svg>
      </div>
      <svg className="w-16 h-16 text-muted-foreground/50 mb-3 relative z-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
      <p className="text-muted-foreground text-sm mb-1 relative z-10">Your fitness data will appear here</p>
      <p className="text-muted-foreground/70 text-xs relative z-10">Upload your first ride to unlock PMC insights</p>
    </div>
  );
}
