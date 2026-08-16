import { useState, useEffect, useRef, useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import type { Activity, GeoJSONFeatureCollection, SameRouteResponse, CompareResponse } from "../api";
import { fetchActivity, fetchActivityRecords, fetchSameRouteActivities, fetchComparison } from "../api";
import { ActivitySelector } from "../components/ActivitySelector";
import { ResizableMap } from "../components/ResizableMap";
import { useResizableMap } from "../hooks/useResizableMap";
import { ChartErrorBoundary } from "../components/ErrorBoundary";
import { Skeleton } from "@/components/ui/skeleton";
import { ChartSkeleton } from "@/components/ui/skeletons";
import { formatDistance, formatTime, formatActivityDate, formatRelativeTime } from "../format";
import {
  PowerComparisonChart, StatsTable, gapColor, formatDistanceKm, formatGap, smoothGapData,
  type GapChartPoint,
} from "../components/compare";

export function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const baseIdParam = searchParams.get("base");
  const compareIdParam = searchParams.get("compare");
  
  const [baseActivity, setBaseActivity] = useState<Activity | null>(null);
  const [compareActivity, setCompareActivity] = useState<Activity | null>(null);
  const [baseGeojson, setBaseGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [compareGeojson, setCompareGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [sameRouteData, setSameRouteData] = useState<SameRouteResponse | null>(null);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [hoveredPosition, setHoveredPosition] = useState<[number, number] | null>(null);
  
  const loadedBaseFromUrl = useRef(false);
  const loadedCompareFromUrl = useRef(false);

  const { height: mapHeight, isResizing, startResizeHeight } = useResizableMap({
    storageKey: "compare-page", defaultHeight: 250, minHeight: 150, maxHeight: 600,
    defaultWidthPercent: 40, minWidthPercent: 25, maxWidthPercent: 60,
  });

  useEffect(() => {
    if (baseIdParam && !loadedBaseFromUrl.current) {
      loadedBaseFromUrl.current = true;
      setLoading(true);
      Promise.all([fetchActivity(baseIdParam), fetchActivityRecords(baseIdParam), fetchSameRouteActivities(baseIdParam)])
        .then(([activity, geojson, sameRoute]) => {
          setBaseActivity(activity); setBaseGeojson(geojson); setSameRouteData(sameRoute);
        })
        .catch((e) => console.error("[ComparePage] Failed to load base activity from URL:", e))
        .finally(() => setLoading(false));
    }
  }, [baseIdParam]);

  useEffect(() => {
    if (compareIdParam && !loadedCompareFromUrl.current && baseActivity) {
      loadedCompareFromUrl.current = true;
      Promise.all([fetchActivity(compareIdParam), fetchActivityRecords(compareIdParam), fetchComparison(baseActivity.id, compareIdParam)])
        .then(([activity, geojson, comp]) => {
          setCompareActivity(activity); setCompareGeojson(geojson); setComparison(comp);
        })
        .catch((e) => console.error("[ComparePage] Failed to load compare activity from URL:", e));
    }
  }, [compareIdParam, baseActivity]);

  const updateSearchParams = (base: Activity | null, compare: Activity | null) => {
    const params: Record<string, string> = {};
    if (base) params.base = base.id;
    if (compare) params.compare = compare.id;
    setSearchParams(params);
  };



  const handleBaseSelect = (activity: Activity | null) => {
    setBaseActivity(activity); setBaseGeojson(null); setSameRouteData(null);
    setCompareActivity(null); setCompareGeojson(null); setComparison(null);
    if (activity) {
      setLoading(true);
      Promise.all([fetchActivityRecords(activity.id), fetchSameRouteActivities(activity.id)])
        .then(([geojson, sameRoute]) => { setBaseGeojson(geojson); setSameRouteData(sameRoute); })
        .catch((e) => console.error("[ComparePage] Failed to load base activity data:", e))
        .finally(() => setLoading(false));
      setSearchParams({ base: activity.id.toString() });
    } else {
      setSearchParams({});
    }
  };

  const handleCompareSelect = (activity: Activity | null) => {
    setCompareGeojson(null); setComparison(null);
    if (activity && baseActivity) {
      setCompareActivity(null);
      Promise.all([fetchActivity(activity.id), fetchActivityRecords(activity.id), fetchComparison(baseActivity.id, activity.id)])
        .then(([fullActivity, geojson, comp]) => {
          setCompareActivity(fullActivity); setCompareGeojson(geojson); setComparison(comp);
        })
        .catch((e) => console.error("[ComparePage] Failed to load compare activity data:", e));
      updateSearchParams(baseActivity, activity);
    } else {
      setCompareActivity(null);
      updateSearchParams(baseActivity, null);
    }
  };

  const handleSwap = () => {
    const tempActivity = baseActivity;
    const tempGeojson = baseGeojson;
    if (compareActivity) {
      setLoading(true);
      fetchSameRouteActivities(compareActivity.id)
        .then((sameRoute) => {
          setBaseActivity(compareActivity); setBaseGeojson(compareGeojson);
          setSameRouteData(sameRoute); setCompareActivity(tempActivity);
          setCompareGeojson(tempGeojson); updateSearchParams(compareActivity, tempActivity);
        })
        .catch((e) => console.error("[ComparePage] Failed to swap activities:", e))
        .finally(() => setLoading(false));
    }
  };

  const basePositions = useMemo(() => {
    if (!baseGeojson) return [];
    return baseGeojson.features.filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]);
  }, [baseGeojson]);

  const comparePositions = useMemo(() => {
    if (!compareGeojson) return [];
    return compareGeojson.features.filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]);
  }, [compareGeojson]);

  const sameRouteActivityIds = useMemo(() => sameRouteData ? sameRouteData.activities.map((a) => a.id) : [], [sameRouteData]);
  const hasSameRouteActivities = sameRouteActivityIds.length > 0;

  const elevationByDistance = useMemo(() => {
    const map = new Map<number, number>();
    if (!baseGeojson) return map;
    for (const f of baseGeojson.features) {
      if (f.properties.altitude_m !== null) map.set(f.properties.distance_m, f.properties.altitude_m);
    }
    return map;
  }, [baseGeojson]);

  const gapChartData = useMemo((): GapChartPoint[] => {
    if (!comparison?.gap_series || comparison.gap_series.length === 0) return [];
    return smoothGapData(comparison.gap_series, elevationByDistance);
  }, [comparison, elevationByDistance]);



  const posByDist = useMemo(() => {
    if (!baseGeojson) return [];
    return baseGeojson.features.filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => ({ distance_m: f.properties.distance_m, pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number] }));
  }, [baseGeojson]);

  const findPositionByDistance = (distance_m: number): [number, number] | null => {
    if (posByDist.length === 0) return null;
    let closest = posByDist[0];
    let minDiff = Math.abs(closest.distance_m - distance_m);
    for (const p of posByDist) {
      const diff = Math.abs(p.distance_m - distance_m);
      if (diff < minDiff) { minDiff = diff; closest = p; }
    }
    return closest.pos;
  };

  const coloredSegments = useMemo(() => {
    if (!comparison?.gap_series || comparison.gap_series.length < 2 || posByDist.length < 2) return [];
    const gapSeries = comparison.gap_series;
    const segments: { positions: [number, number][]; color: string }[] = [];
    for (let i = 0; i < gapSeries.length - 1; i++) {
      const distStart = gapSeries[i].distance_m;
      const distEnd = gapSeries[i + 1].distance_m;
      const color = gapColor(gapSeries[i].gap_s);
      const pointsInSegment: [number, number][] = [];
      for (const p of posByDist) {
        if (p.distance_m >= distStart && p.distance_m <= distEnd) pointsInSegment.push(p.pos);
      }
      if (pointsInSegment.length >= 2) segments.push({ positions: pointsInSegment, color });
    }
    return segments;
  }, [comparison, posByDist]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleChartHover = (state: any) => {
    if (state?.activePayload?.[0]?.payload) {
      const point = state.activePayload[0].payload as GapChartPoint;
      const pos = findPositionByDistance(point.distance_m);
      setHoveredPosition(pos);
    }
  };
  const handleChartLeave = () => setHoveredPosition(null);

  return (
    <div className="h-full flex flex-col bg-background">
      <div className="flex-shrink-0 p-8 pb-0">
        <h1 className="text-page-title mb-2">Compare Activities</h1>
        <p className="text-muted-foreground">Compare performance metrics between two activities</p>
      </div>

      {basePositions.length > 0 && (
        <div className="flex-shrink-0 px-8 pt-6 pb-0 relative">
          <ResizableMap positions={basePositions} coloredSegments={coloredSegments.length > 0 ? coloredSegments : undefined}
            otherPositions={comparePositions.length > 0 && coloredSegments.length === 0 ? comparePositions : null}
            hoveredPosition={hoveredPosition} height={mapHeight} onResizeStart={startResizeHeight} isResizing={isResizing} />
          {coloredSegments.length > 0 && (
            <div className="absolute bottom-6 left-12 z-[1000] bg-card/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-border shadow-lg">
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-[#10b981]" /><span className="text-foreground">Ahead</span></div>
                <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-[#6366f1]" /><span className="text-foreground">Even</span></div>
                <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-[#ef4444]" /><span className="text-foreground">Behind</span></div>
              </div>
            </div>
          )}
        </div>
      )}



      {/* Control bar with activity selectors */}
      <div className="flex-shrink-0 px-8 py-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <ActivitySelector selectedId={baseActivity?.id ?? null} onSelect={handleBaseSelect} excludeIds={compareActivity ? [compareActivity.id] : []}
              label="" placeholder="Select the base ride..." className="border-2 border-primary/30 rounded-xl focus-within:ring-2 focus-within:ring-primary/50" />
          </div>
          <div>
            {baseActivity ? (
              hasSameRouteActivities ? (
                <ActivitySelector selectedId={compareActivity?.id ?? null} onSelect={handleCompareSelect} filterIds={sameRouteActivityIds}
                  excludeIds={[baseActivity.id]} label="" placeholder="Select ride to compare..." className="border-2 border-border rounded-xl focus-within:ring-2 focus-within:ring-accent/50" />
              ) : (
                <div className="px-4 py-3 bg-muted rounded-xl border-2 border-border text-muted-foreground text-sm">No other rides on this route yet. Select a different base activity.</div>
              )
            ) : (
              <div className="px-4 py-3 bg-muted rounded-xl border-2 border-border text-muted-foreground text-sm">Select a base activity first</div>
            )}
          </div>
        </div>
        {baseActivity && compareActivity && (
          <div className="flex justify-center mt-6">
            <button onClick={handleSwap} disabled={loading} className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground bg-card border border-border rounded-lg hover:bg-muted transition-fast disabled:opacity-50">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" /></svg>
              Swap Activities
            </button>
          </div>
        )}
      </div>

      {/* Comparison content area */}
      <div className="flex-1 min-h-0 px-8 pb-8 overflow-y-auto">
        {/* Suggested Comparisons */}
        {baseActivity && !compareActivity && sameRouteData && (
          <div className="mb-8">
            <h3 className="text-lg font-semibold mb-2">Suggested Comparisons</h3>
            <p className="text-body-secondary mb-4">Activities similar to your selected ride</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {sameRouteData.activities.slice(0, 3).map((activity) => (
                <div key={activity.id} onClick={() => handleCompareSelect(activity)} className="bg-card rounded-xl border border-border p-4 card-hover cursor-pointer hover:border-primary/50 transition-all duration-300">
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-16 h-12 bg-muted/30 rounded-lg overflow-hidden flex-shrink-0 flex items-center justify-center">
                      <svg className="w-8 h-8 text-primary/50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>
                    </div>
                    <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full flex items-center gap-1">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" /></svg>
                      Same Route
                    </span>
                  </div>
                  <h4 className="font-medium mb-1 truncate">{activity.title || formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: "short", month: "short", day: "numeric" })}</h4>
                  <p className="text-body-secondary mb-3">{formatRelativeTime(activity.started_at)}</p>
                  <div className="flex gap-3 text-caption">
                    <div>{formatDistance(activity.total_distance_m)}</div>
                    <div>{formatTime(activity.moving_time_s)}</div>
                    <div>{activity.avg_power_w ? `${Math.round(activity.avg_power_w)}W` : "—"}</div>
                  </div>
                </div>
              ))}
              {sameRouteData.activities.length === 0 && (
                <div className="col-span-full text-center py-8 text-muted-foreground"><p>No same-route activities found. Try selecting a different base activity.</p></div>
              )}
            </div>
          </div>
        )}



        {loading ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-card rounded-lg border border-border p-4">
                <div className="flex items-center gap-2 mb-2"><Skeleton className="w-3 h-3 rounded-full" /><Skeleton className="h-3 w-12" /></div>
                <Skeleton className="h-6 w-48 mb-1" /><Skeleton className="h-4 w-32" />
              </div>
              <div className="bg-card rounded-lg border border-border p-4">
                <div className="flex items-center gap-2 mb-2"><Skeleton className="w-3 h-3 rounded-full" /><Skeleton className="h-3 w-16" /></div>
                <Skeleton className="h-6 w-48 mb-1" /><Skeleton className="h-4 w-32" />
              </div>
            </div>
            <div className="bg-card rounded-lg border border-border p-4">
              <Skeleton className="h-5 w-40 mb-4" /><ChartSkeleton height="h-64" />
            </div>
          </div>
        ) : baseActivity && compareActivity ? (
          <div className="space-y-4">
            {/* Activities summary cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Link to={`/activities/${baseActivity.id}`} className="bg-card rounded-lg border border-border p-4 card-hover cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:shadow-xl block">
                <div className="flex items-center gap-2 mb-2"><span className="w-3 h-3 rounded-full bg-indigo-500" /><span className="text-metric-label text-primary">Base</span></div>
                <h3 className="text-lg font-semibold text-foreground">{baseActivity.title || "Untitled"}</h3>
                <p className="text-body-secondary">{formatActivityDate(baseActivity.started_at, baseActivity.utc_offset_minutes, { weekday: "short", year: "numeric", month: "short", day: "numeric" })}</p>
              </Link>
              <Link to={`/activities/${compareActivity.id}`} className="bg-card rounded-lg border border-border p-4 card-hover cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:shadow-xl block">
                <div className="flex items-center gap-2 mb-2"><span className="w-3 h-3 rounded-full bg-amber-500" /><span className="text-metric-label text-warning">Compare</span></div>
                <h3 className="text-lg font-semibold text-foreground">{compareActivity.title || "Untitled"}</h3>
                <p className="text-body-secondary">{formatActivityDate(compareActivity.started_at, compareActivity.utc_offset_minutes, { weekday: "short", year: "numeric", month: "short", day: "numeric" })}</p>
              </Link>
            </div>

            {/* Gap Chart */}
            {comparison?.comparable && gapChartData.length > 0 && (
              <ChartErrorBoundary>
                <div className="bg-card rounded-lg border border-border p-4">
                  <h3 className="text-sm font-medium text-foreground mb-3">Time Gap vs Distance</h3>
                  <div style={{ height: 350 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={gapChartData} onMouseMove={handleChartHover} onMouseLeave={handleChartLeave} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                        <XAxis dataKey="distance_m" tickFormatter={formatDistanceKm} stroke="#9ca3af" fontSize={12} />
                        <YAxis yAxisId="gap" stroke="#9ca3af" fontSize={12} tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}s`} domain={["auto", "auto"]} />
                        <YAxis yAxisId="elevation" orientation="right" stroke="#9ca3af" fontSize={12} tickFormatter={(v) => `${Math.round(v)}m`} domain={["dataMin - 50", "dataMax + 50"]} />
                        <Tooltip contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: "0.375rem", color: "#f9fafb" }}
                          formatter={(value, name) => {
                            if (name === "gap_s") { const gap = value as number; return [`${formatGap(gap)} ${gap < 0 ? "ahead" : "behind"}`, "Gap"]; }
                            if (name === "elevation_m") return [`${Math.round(value as number)} m`, "Elevation"];
                            return [value, name];
                          }}
                          labelFormatter={(label) => formatDistanceKm(label as number)} />
                        <ReferenceLine y={0} yAxisId="gap" stroke="#6366f1" strokeDasharray="3 3" />
                        <Area type="monotone" dataKey="elevation_m" yAxisId="elevation" fill="#10b981" fillOpacity={0.15} stroke="#10b981" strokeWidth={1} strokeOpacity={0.5} />
                        <Line type="monotone" dataKey="gap_s" yAxisId="gap" stroke="#f59e0b" strokeWidth={2} dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </ChartErrorBoundary>
            )}

            <PowerComparisonChart baseGeojson={baseGeojson} compareGeojson={compareGeojson} baseActivity={baseActivity} compareActivity={compareActivity} onHover={handleChartHover} onLeave={handleChartLeave} />
            <StatsTable baseActivity={baseActivity} compareActivity={compareActivity} comparison={comparison} />
          </div>


        ) : !baseActivity ? (
          <div className="bg-card border border-border rounded-xl p-12">
            <div className="max-w-3xl mx-auto text-center">
              <svg className="w-24 h-24 text-muted-foreground/50 mx-auto mb-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/>
              </svg>
              <h2 className="text-2xl font-bold mb-3 text-foreground">Select Two Activities to Compare</h2>
              <p className="text-muted-foreground mb-8">Choose a base activity above, then select another to compare performance, routes, and training load.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left max-w-2xl mx-auto">
                <div className="bg-muted/30 rounded-lg p-5 border-l-4 border-primary">
                  <h3 className="font-semibold mb-2 flex items-center gap-2 text-foreground"><div className="w-2 h-2 rounded-full bg-primary" />What You Can Compare</h3>
                  <ul className="space-y-2 text-body-secondary">
                    <li className="flex items-start gap-2"><svg className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg><span>Power profiles and zones</span></li>
                    <li className="flex items-start gap-2"><svg className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg><span>Heart rate distribution</span></li>
                    <li className="flex items-start gap-2"><svg className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg><span>Speed and elevation profiles</span></li>
                  </ul>
                </div>
                <div className="bg-muted/30 rounded-lg p-5 border-l-4 border-accent">
                  <h3 className="font-semibold mb-2 flex items-center gap-2 text-foreground"><div className="w-2 h-2 rounded-full bg-accent" />Comparison Tips</h3>
                  <ul className="space-y-2 text-body-secondary">
                    <li className="flex items-start gap-2"><svg className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>Same route on different days</span></li>
                    <li className="flex items-start gap-2"><svg className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>Track fitness improvements</span></li>
                    <li className="flex items-start gap-2"><svg className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>Different pacing strategies</span></li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-64 bg-card rounded-xl border border-border">
            <p className="text-muted-foreground">Select an activity to compare with from the suggestions above.</p>
          </div>
        )}
      </div>
    </div>
  );
}
