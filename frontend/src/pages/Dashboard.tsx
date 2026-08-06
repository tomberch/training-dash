import { useState, useEffect, useMemo } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceArea,
} from "recharts";
import type { Activity, PMCPoint, PowerCurvePoint, Notification, RecordsResponse, ThresholdEntry } from "../api";
import { 
  fetchActivities, 
  fetchPMC, 
  fetchPowerCurve, 
  fetchNotifications,
  acceptNotification,
  dismissNotification,
  fetchRecords,
  fetchThresholds,
} from "../api";
import { PolylineMap } from "../components/PolylineMap";
import { formatDuration, formatDistance, formatRelativeTime, formatElevation } from "../format";
import { TSB_ZONES, getTSBZone } from "../constants";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function DashboardLoadingSkeleton() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header */}
      <Skeleton className="h-8 w-32 mb-6" />
      
      {/* Top Row: PMC + Weekly Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* PMC Sparkline skeleton */}
        <div className="lg:col-span-2 bg-card rounded-lg border border-border p-4">
          <div className="flex items-center justify-between mb-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-6 w-20 rounded-full" />
          </div>
          <div className="h-40 bg-muted rounded flex items-end justify-around p-4 gap-1">
            {[40, 55, 35, 60, 45, 70, 50, 65, 45, 75, 55, 80].map((h, i) => (
              <Skeleton key={i} className="w-3 rounded-t" style={{ height: `${h}%` }} />
            ))}
          </div>
          <div className="flex gap-6 mt-2">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
        
        {/* Weekly Summary skeleton */}
        <div className="bg-card rounded-lg border border-border p-4">
          <Skeleton className="h-4 w-20 mb-3" />
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex justify-between">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-12" />
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Recent Activities */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <Skeleton className="h-6 w-36" />
          <Skeleton className="h-4 w-16" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-card rounded-xl border border-border overflow-hidden">
              <Skeleton className="h-32 rounded-none" />
              <div className="p-4 space-y-3">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-3 w-32" />
                <div className="grid grid-cols-4 gap-2">
                  {[1, 2, 3, 4].map((j) => (
                    <div key={j} className="text-center">
                      <Skeleton className="h-4 w-12 mx-auto mb-1" />
                      <Skeleton className="h-3 w-10 mx-auto" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Power Curve thumbnail skeleton */}
      <div className="bg-card rounded-lg border border-border p-4">
        <Skeleton className="h-4 w-24 mb-2" />
        <div className="h-24 bg-muted rounded flex items-end justify-around p-2 gap-0.5">
          {[95, 85, 75, 68, 62, 58, 55, 52, 50, 48, 46, 44, 42, 40, 38].map((h, i) => (
            <Skeleton key={i} className="flex-1 rounded-t" style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [pmcData, setPmcData] = useState<PMCPoint[]>([]);
  const [powerCurve, setPowerCurve] = useState<PowerCurvePoint[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [records, setRecords] = useState<RecordsResponse | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch last 8 weeks of PMC data for sparkline
    const today = new Date();
    const eightWeeksAgo = new Date(today);
    eightWeeksAgo.setDate(eightWeeksAgo.getDate() - 56);
    
    Promise.all([
      fetchActivities(),
      fetchPMC(eightWeeksAgo.toISOString().split("T")[0], today.toISOString().split("T")[0]),
      fetchPowerCurve(),
      fetchNotifications(),
      fetchRecords(),
      fetchThresholds().catch(() => []),
    ])
      .then(([acts, pmc, curve, notifs, recs, thresh]) => {
        setActivities(acts.activities);
        setPmcData(pmc);
        setPowerCurve(curve);
        setNotifications(notifs);
        setRecords(recs);
        setThresholds(thresh);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Current PMC values (latest point)
  const currentPMC = pmcData.length > 0 ? pmcData[pmcData.length - 1] : null;
  const currentZone = currentPMC ? getTSBZone(currentPMC.tsb) : null;

  // Previous PMC (7 days ago) for trend calculation
  const previousPMC = pmcData.length > 7 ? pmcData[pmcData.length - 8] : null;
  const ctlTrend = currentPMC && previousPMC 
    ? ((currentPMC.ctl - previousPMC.ctl) / (previousPMC.ctl || 1) * 100)
    : null;

  // Recent activities (top 4 for card grid)
  const recentActivities = activities.slice(0, 4);

  // Recent breakthrough activities (last 30 days)
  const recentBreakthroughs = useMemo(() => {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    return activities
      .filter(a => a.is_breakthrough && new Date(a.started_at) >= thirtyDaysAgo)
      .slice(0, 3);
  }, [activities]);

  // Notable PRs from records
  const notablePRs = useMemo(() => {
    if (!records) return [];
    const prs: { label: string; value: string; activityId?: string }[] = [];
    const { lifetime_prs } = records;
    
    if (lifetime_prs.highest_sustained_power_w) {
      prs.push({
        label: "Best Power",
        value: `${lifetime_prs.highest_sustained_power_w.value} W`,
        activityId: lifetime_prs.highest_sustained_power_w.activity_id,
      });
    }
    if (lifetime_prs.longest_distance_m) {
      prs.push({
        label: "Longest Ride",
        value: formatDistance(lifetime_prs.longest_distance_m.value),
        activityId: lifetime_prs.longest_distance_m.activity_id,
      });
    }
    if (lifetime_prs.biggest_elevation_gain_m) {
      prs.push({
        label: "Most Climbing",
        value: `${Math.round(lifetime_prs.biggest_elevation_gain_m.value)} m`,
        activityId: lifetime_prs.biggest_elevation_gain_m.activity_id,
      });
    }
    return prs.slice(0, 3);
  }, [records]);

  // Weekly summary
  const weeklySummary = useMemo(() => {
    const now = new Date();
    const startOfWeek = new Date(now);
    startOfWeek.setDate(now.getDate() - now.getDay());
    startOfWeek.setHours(0, 0, 0, 0);
    
    const startOfLastWeek = new Date(startOfWeek);
    startOfLastWeek.setDate(startOfLastWeek.getDate() - 7);

    const thisWeek = activities.filter(a => new Date(a.started_at) >= startOfWeek);
    const lastWeek = activities.filter(a => {
      const d = new Date(a.started_at);
      return d >= startOfLastWeek && d < startOfWeek;
    });

    return {
      thisWeek: {
        count: thisWeek.length,
        duration: thisWeek.reduce((sum, a) => sum + a.moving_time_s, 0),
        tss: thisWeek.reduce((sum, a) => sum + (a.tss || 0), 0),
        distance: thisWeek.reduce((sum, a) => sum + a.total_distance_m, 0),
      },
      lastWeek: {
        count: lastWeek.length,
        duration: lastWeek.reduce((sum, a) => sum + a.moving_time_s, 0),
        tss: lastWeek.reduce((sum, a) => sum + (a.tss || 0), 0),
        distance: lastWeek.reduce((sum, a) => sum + a.total_distance_m, 0),
      },
    };
  }, [activities]);

  // Handle notification actions
  const handleAcceptNotification = async (id: number) => {
    await acceptNotification(id);
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const handleDismissNotification = async (id: number) => {
    await dismissNotification(id);
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  if (loading) {
    return <DashboardLoadingSkeleton />;
  }

  // Empty state when no activities
  if (activities.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-primary/10 mb-6">
            <svg className="w-10 h-10 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-foreground mb-3">Welcome to TrainDash</h1>
          <p className="text-lg text-muted-foreground max-w-md mx-auto">
            Get started by uploading your first activity or connecting to Xert/Garmin to sync automatically.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {/* Step 1: Set thresholds */}
          <div 
            className="bg-card rounded-xl border border-border p-6 cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => navigate("/settings")}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">1</div>
              <h3 className="font-semibold text-foreground">Set Your FTP</h3>
            </div>
            <p className="text-sm text-muted-foreground">
              Configure your power thresholds to enable TSS, training load, and performance tracking.
            </p>
          </div>

          {/* Step 2: Connect or upload */}
          <div 
            className="bg-card rounded-xl border border-border p-6 cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => navigate("/settings")}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">2</div>
              <h3 className="font-semibold text-foreground">Connect Accounts</h3>
            </div>
            <p className="text-sm text-muted-foreground">
              Link your Xert or Garmin account to automatically sync your rides.
            </p>
          </div>

          {/* Step 3: Upload manually */}
          <div className="bg-card rounded-xl border border-border p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-muted-foreground text-sm font-bold">or</div>
              <h3 className="font-semibold text-foreground">Upload FIT Files</h3>
            </div>
            <p className="text-sm text-muted-foreground">
              Use the "Upload FIT" button in the header to manually upload activity files.
            </p>
          </div>
        </div>

        {/* Quick stats preview */}
        <div className="bg-primary/5 rounded-xl border border-primary/20 p-6">
          <h3 className="font-semibold text-foreground mb-4">What you'll see here</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center gap-2 text-muted-foreground">
              <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span>Performance chart</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              <span>Power curve</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Weekly summary</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Recent activities</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-bold text-foreground mb-6">Dashboard</h1>

      {/* Onboarding: Prompt to set thresholds */}
      {thresholds.length === 0 && (
        <Card className="mb-6 border-primary/30 bg-primary/5">
          <CardContent className="flex items-center justify-between py-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/20">
                <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h3 className="font-medium text-foreground">Set your training thresholds</h3>
                <p className="text-sm text-muted-foreground">
                  Add your FTP, LTHR, and HRmax to enable TSS, training zones, and performance metrics.
                </p>
              </div>
            </div>
            <Button variant="default" size="sm" asChild>
              <Link to="/settings">Configure</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Notifications Banner */}
      {notifications.length > 0 && (
        <div className="mb-6 space-y-2">
          {notifications.map(notif => (
            <div 
              key={notif.id}
              className="flex items-center justify-between p-4 bg-warning/10 border border-warning/30 rounded-lg"
            >
              <div className="flex items-center gap-3">
                <svg className="w-5 h-5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm text-warning-foreground">{notif.message}</span>
              </div>
              <div className="flex items-center gap-2">
                {notif.payload?.suggested_ftp && (
                  <button
                    onClick={() => handleAcceptNotification(notif.id)}
                    className="px-3 py-1 text-xs font-medium text-white bg-warning hover:bg-warning/80 rounded-lg transition-fast"
                  >
                    Apply {notif.payload.suggested_ftp}W
                  </button>
                )}
                <button
                  onClick={() => handleDismissNotification(notif.id)}
                  className="px-3 py-1 text-xs font-medium text-warning-foreground hover:bg-warning/20 rounded-lg transition-fast"
                >
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Top Row: PMC Sparkline + Current Form + Weekly Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* PMC Sparkline */}
        <div 
          className="lg:col-span-2 bg-card rounded-lg border border-border p-4 cursor-pointer card-interactive"
          onClick={() => navigate("/pmc")}
        >
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-medium text-muted-foreground">Performance Management</h2>
            {currentZone && (
              <span
                className="px-2 py-1 text-xs font-semibold rounded-full"
                style={{ backgroundColor: currentZone.color, color: "#1f2937" }}
              >
                {currentZone.name}
              </span>
            )}
          </div>
          
          {pmcData.length > 0 ? (
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={pmcData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                  {TSB_ZONES.map((zone) => (
                    <ReferenceArea
                      key={zone.name}
                      y1={zone.min}
                      y2={zone.max}
                      fill={zone.color}
                      fillOpacity={0.2}
                      ifOverflow="hidden"
                    />
                  ))}
                  <XAxis dataKey="date" hide />
                  <YAxis domain={[-30, 50]} hide />
                  <Line type="monotone" dataKey="tsb" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="ctl" stroke="#3b82f6" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">
              No data available
            </div>
          )}
          
          {currentPMC && (
            <div className="flex gap-6 mt-2 text-sm">
              <div>
                <span className="text-muted-foreground">CTL </span>
                <span className="font-medium text-chart-ctl">{currentPMC.ctl.toFixed(0)}</span>
                {ctlTrend !== null && (
                  <span className={`ml-1 text-xs ${ctlTrend > 0 ? "text-success" : ctlTrend < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                    {ctlTrend > 0 ? "↑" : ctlTrend < 0 ? "↓" : "→"}{Math.abs(ctlTrend).toFixed(1)}%
                  </span>
                )}
              </div>
              <div>
                <span className="text-muted-foreground">ATL </span>
                <span className="font-medium text-chart-atl">{currentPMC.atl.toFixed(0)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">TSB </span>
                <span className="font-medium text-chart-tsb">{currentPMC.tsb.toFixed(0)}</span>
              </div>
            </div>
          )}
        </div>

        {/* Weekly Summary */}
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-muted-foreground mb-3">This Week</h2>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Rides</span>
              <span className="font-medium text-foreground">{weeklySummary.thisWeek.count}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Time</span>
              <div className="text-right">
                <span className="font-medium text-foreground">{formatDuration(weeklySummary.thisWeek.duration)}</span>
                {weeklySummary.lastWeek.duration > 0 && (
                  <span className={`ml-2 text-xs ${weeklySummary.thisWeek.duration >= weeklySummary.lastWeek.duration ? "text-success" : "text-destructive"}`}>
                    vs {formatDuration(weeklySummary.lastWeek.duration)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">TSS</span>
              <div className="text-right">
                <span className="font-medium text-foreground">{Math.round(weeklySummary.thisWeek.tss)}</span>
                {weeklySummary.lastWeek.tss > 0 && (
                  <span className={`ml-2 text-xs ${weeklySummary.thisWeek.tss >= weeklySummary.lastWeek.tss ? "text-success" : "text-destructive"}`}>
                    vs {Math.round(weeklySummary.lastWeek.tss)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Distance</span>
              <span className="font-medium text-foreground">{formatDistance(weeklySummary.thisWeek.distance)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activities - Card Grid */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Recent Activities</h2>
          <button 
            onClick={() => navigate("/activities")}
            className="text-sm text-primary hover:underline"
          >
            View all
          </button>
        </div>
        
        {recentActivities.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recentActivities.map(activity => (
              <div 
                key={activity.id}
                className="bg-card rounded-xl border border-border overflow-hidden cursor-pointer card-interactive"
                onClick={() => navigate(`/activities/${activity.id}`)}
              >
                {/* Map thumbnail */}
                <div className="h-32 relative">
                  <PolylineMap 
                    polyline={activity.map_polyline} 
                    className="w-full h-full" 
                    showMarkers={true}
                  />
                  {/* Breakthrough badge overlay */}
                  {activity.is_breakthrough && (
                    <div className="absolute top-2 right-2">
                      <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-warning-foreground bg-warning/90 rounded-full shadow">
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        Breakthrough
                      </span>
                    </div>
                  )}
                  {/* Relative time badge */}
                  <div className="absolute bottom-2 left-2">
                    <span className="px-2 py-1 text-xs font-medium text-white bg-black/60 rounded-full">
                      {formatRelativeTime(activity.started_at)}
                    </span>
                  </div>
                </div>
                
                {/* Activity info */}
                <div className="p-4">
                  {/* Title */}
                  <h3 className="text-base font-semibold text-foreground truncate mb-1">
                    {activity.title || new Date(activity.started_at).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
                  </h3>
                  
                  {/* Date if title exists */}
                  {activity.title && (
                    <p className="text-sm text-muted-foreground mb-3">
                      {new Date(activity.started_at).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
                    </p>
                  )}
                  
                  {/* Metrics grid */}
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div>
                      <div className="text-sm font-semibold text-foreground tabular-nums">
                        {formatDistance(activity.total_distance_m)}
                      </div>
                      <div className="text-xs text-muted-foreground">Distance</div>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-foreground tabular-nums">
                        {formatDuration(activity.moving_time_s)}
                      </div>
                      <div className="text-xs text-muted-foreground">Time</div>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-foreground tabular-nums">
                        {formatElevation(activity.elevation_gain_m)}
                      </div>
                      <div className="text-xs text-muted-foreground">Elevation</div>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-foreground tabular-nums">
                        {activity.tss ? Math.round(activity.tss) : "—"}
                      </div>
                      <div className="text-xs text-muted-foreground">TSS</div>
                    </div>
                  </div>
                  
                  {/* Secondary metrics row */}
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-border">
                    <div className="flex items-center gap-4 text-sm">
                      {activity.avg_power_w && (
                        <span className="text-muted-foreground">
                          <span className="font-medium text-foreground">{activity.avg_power_w}</span> W
                        </span>
                      )}
                      {activity.avg_hr_bpm && (
                        <span className="text-muted-foreground">
                          <span className="font-medium text-foreground">{activity.avg_hr_bpm}</span> bpm
                        </span>
                      )}
                      {activity.np_power_w && (
                        <span className="text-muted-foreground">
                          NP <span className="font-medium text-foreground">{activity.np_power_w}</span>
                        </span>
                      )}
                    </div>
                    {activity.intensity_factor && (
                      <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                        IF {activity.intensity_factor.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-card rounded-xl border border-border p-8 text-center">
            <p className="text-muted-foreground">No activities yet. Upload a FIT file to get started.</p>
          </div>
        )}
      </div>

      {/* What's Notable Section */}
      {(recentBreakthroughs.length > 0 || notablePRs.length > 0) && (
        <div className="bg-card rounded-lg border border-border p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-muted-foreground">What's Notable</h2>
            <button 
              onClick={() => navigate("/records")}
              className="text-xs text-primary hover:underline"
            >
              All records
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Breakthroughs */}
            {recentBreakthroughs.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-warning uppercase tracking-wide mb-2 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  Recent Breakthroughs
                </h3>
                <div className="space-y-2">
                  {recentBreakthroughs.map(activity => (
                    <div 
                      key={activity.id}
                      className="flex items-center justify-between p-2 rounded-lg bg-warning/10 cursor-pointer hover:bg-warning/20 transition-fast"
                      onClick={() => navigate(`/activities/${activity.id}`)}
                    >
                      <div className="text-sm">
                        <div className="font-medium text-foreground">
                          {activity.title || new Date(activity.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(activity.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        </div>
                      </div>
                      <span className="text-xs font-medium text-warning">
                        {activity.tss ? `${Math.round(activity.tss)} TSS` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Lifetime PRs */}
            {notablePRs.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-primary uppercase tracking-wide mb-2 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                  </svg>
                  Lifetime PRs
                </h3>
                <div className="space-y-2">
                  {notablePRs.map((pr, i) => (
                    <div 
                      key={i}
                      className="flex items-center justify-between p-2 rounded-lg bg-primary/10 cursor-pointer hover:bg-primary/20 transition-fast"
                      onClick={() => pr.activityId && navigate(`/activities/${pr.activityId}`)}
                    >
                      <span className="text-sm text-muted-foreground">{pr.label}</span>
                      <span className="text-sm font-medium text-foreground">{pr.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Bottom Row: Power Curve Thumbnail */}
      <div 
        className="bg-card rounded-lg border border-border p-4 cursor-pointer card-interactive"
        onClick={() => navigate("/power-curve")}
      >
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-medium text-muted-foreground">Power Curve</h2>
          <span className="text-xs text-primary">View full →</span>
        </div>
        {powerCurve.length > 0 ? (
          <div className="h-32 overflow-hidden">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart 
                data={powerCurve.map(p => ({ ...p, logDuration: Math.log10(p.duration_seconds) }))}
                margin={{ top: 10, right: 15, bottom: 5, left: 5 }}
              >
                <XAxis 
                  dataKey="logDuration" 
                  type="number"
                  domain={[Math.log10(5), Math.log10(7200)]}
                  hide 
                />
                <YAxis 
                  domain={['dataMin - 50', 'dataMax + 50']}
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  axisLine={false}
                  tickLine={false}
                  width={35}
                />
                <Line 
                  type="monotone" 
                  dataKey="watts" 
                  stroke="#6366f1" 
                  strokeWidth={2} 
                  dot={{ fill: "#6366f1", r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
            No power data available
          </div>
        )}
        {powerCurve.length > 0 && (
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>5s: {powerCurve.find(p => p.duration_seconds === 5)?.watts || "—"}W</span>
            <span>1m: {powerCurve.find(p => p.duration_seconds === 60)?.watts || "—"}W</span>
            <span>5m: {powerCurve.find(p => p.duration_seconds === 300)?.watts || "—"}W</span>
            <span>20m: {powerCurve.find(p => p.duration_seconds === 1200)?.watts || "—"}W</span>
          </div>
        )}
      </div>
    </div>
  );
}
