import type { JSX } from "react";
import { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceLine,
} from "recharts";
import { toast } from "sonner";
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
import { PageHeader } from "../components/PageHeader";
import { formatDuration, formatDistance, formatRelativeTime, formatElevation, formatActivityDate } from "../format";
import { TSB_ZONES, getTSBZone } from "../constants";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

interface DashboardProps {
  // No props needed - header is now global
}

function DashboardLoadingSkeleton(): JSX.Element {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <Skeleton className="h-9 w-40" />
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-28 rounded-lg" />
          <Skeleton className="h-10 w-10 rounded-full" />
        </div>
      </div>
      
      {/* Top Row: PMC + Weekly Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* PMC Sparkline skeleton */}
        <div className="lg:col-span-2 bg-card rounded-xl border border-border p-6">
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
        <div className="bg-card rounded-xl border border-border p-6">
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
      <div className="bg-card rounded-xl border border-border p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <Skeleton className="h-6 w-36" />
          <Skeleton className="h-4 w-16" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-muted/30 rounded-xl border border-border overflow-hidden">
              <Skeleton className="h-40 rounded-none" />
              <div className="p-4 space-y-3">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-3 w-32" />
                <div className="grid grid-cols-3 gap-2">
                  {[1, 2, 3].map((j) => (
                    <div key={j} className="text-center">
                      <Skeleton className="h-3 w-12 mx-auto" />
                    </div>
                  ))}
                </div>
                <div className="pt-3 border-t border-border">
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Power Curve thumbnail skeleton */}
      <div className="bg-card rounded-xl border border-border p-6">
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

export function Dashboard({}: DashboardProps): JSX.Element {
  const navigate = useNavigate();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [pmcData, setPmcData] = useState<PMCPoint[]>([]);
  const [powerCurve, setPowerCurve] = useState<PowerCurvePoint[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [records, setRecords] = useState<RecordsResponse | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Track if we've shown the first-activity celebration
  const celebrationShownRef = useRef(false);

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
        
        // First-activity celebration: show once when user goes from 0→1+ activities
        const hasSeenCelebration = localStorage.getItem("traindash:first-activity-celebrated");
        if (
          !celebrationShownRef.current &&
          !hasSeenCelebration &&
          acts.activities.length > 0
        ) {
          celebrationShownRef.current = true;
          localStorage.setItem("traindash:first-activity-celebrated", "true");
          toast.success("Your first activity is here! 🎉", {
            description: "Your training journey begins. Explore your ride data below.",
            duration: 5000,
          });
        }
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
      <div className="p-8">
        {/* Header Row */}
        <PageHeader
          title="Dashboard"
        />

        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-primary/10 mb-6">
            <svg className="w-10 h-10 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h2 className="text-page-title mb-3">Welcome to TrainDash</h2>
          <p className="text-lg text-muted-foreground max-w-md mx-auto">
            Get started by uploading your first activity or connecting to Xert/Garmin to sync automatically.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12 max-w-4xl mx-auto">
          {/* Step 1: Set thresholds */}
          <div 
            className="bg-card rounded-xl border border-border p-6 cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => navigate("/settings")}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">1</div>
              <h3 className="font-semibold text-foreground">Set Your FTP</h3>
            </div>
            <p className="text-body-secondary">
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
            <p className="text-body-secondary">
              Link your Xert or Garmin account to automatically sync your rides.
            </p>
          </div>

          {/* Step 3: Upload manually */}
          <div className="bg-card rounded-xl border border-border p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-muted-foreground text-sm font-bold">or</div>
              <h3 className="font-semibold text-foreground">Upload FIT Files</h3>
            </div>
            <p className="text-body-secondary">
              Use the "Upload FIT" button in the header to manually upload activity files.
            </p>
          </div>
        </div>

        {/* Quick stats preview */}
        <div className="bg-primary/5 rounded-xl border border-primary/20 p-6 max-w-4xl mx-auto">
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
    <div className="p-8">
      {/* Header Row */}
      <PageHeader
        title="Dashboard"
      />

      {/* Onboarding: Prompt to set thresholds */}
      {thresholds.length === 0 && (
        <div className="gradient-bg border border-primary/30 rounded-xl p-6 mb-8 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-primary/20 rounded-full flex items-center justify-center flex-shrink-0">
              <svg className="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-lg text-foreground mb-1">Set your training thresholds</h3>
              <p className="text-muted-foreground">
                Add your FTP, LTHR, and HRmax to enable TSS, training zones, and performance metrics.
              </p>
            </div>
          </div>
          <Button variant="default" size="default" className="ml-4 whitespace-nowrap" asChild>
            <Link to="/settings">Configure</Link>
          </Button>
        </div>
      )}

      {/* Notifications Banner */}
      {notifications.length > 0 && (
        <div className="mb-8 space-y-2">
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
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => handleAcceptNotification(notif.id)}
                    className="h-7 text-xs bg-warning text-warning-foreground hover:bg-warning/80"
                  >
                    Apply {notif.payload.suggested_ftp}W
                  </Button>
                )}
                {notif.payload?.suggested_hrmax && (
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => handleAcceptNotification(notif.id)}
                    className="h-7 text-xs bg-warning text-warning-foreground hover:bg-warning/80"
                  >
                    Apply {notif.payload.suggested_hrmax} bpm
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDismissNotification(notif.id)}
                  className="h-7 text-xs text-warning-foreground hover:bg-warning/20"
                >
                  Dismiss
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Top Row: PMC Sparkline + Current Form + Weekly Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
        {/* PMC Sparkline */}
        <div 
          className="lg:col-span-2 bg-card rounded-xl border border-border p-6 cursor-pointer card-hover"
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
            <div className="h-48 bg-muted/30 rounded-lg mb-4 overflow-hidden">
              <ResponsiveContainer width="100%" height={192}>
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
                  <ReferenceLine
                    x={new Date().toISOString().split("T")[0]}
                    stroke="var(--color-success)"
                    strokeWidth={2}
                  />
                  <Line type="monotone" dataKey="tsb" stroke="var(--color-chart-tsb)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="ctl" stroke="var(--color-chart-ctl)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
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
          )}
          
          {currentPMC ? (
            <div className="flex gap-6 mt-4">
              <div>
                <span className="text-muted-foreground text-sm">CTL</span>
                <p className="text-2xl font-bold text-chart-ctl">
                  {currentPMC.ctl.toFixed(0)}
                  {ctlTrend !== null && (
                    <span className={`ml-2 text-sm font-normal ${ctlTrend > 0 ? "text-success" : ctlTrend < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                      {ctlTrend > 0 ? "↑" : ctlTrend < 0 ? "↓" : "→"} {Math.abs(ctlTrend).toFixed(1)}%
                    </span>
                  )}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground text-sm">ATL</span>
                <p className="text-2xl font-bold text-chart-atl">{currentPMC.atl.toFixed(0)}</p>
              </div>
              <div>
                <span className="text-muted-foreground text-sm">TSB</span>
                <p className="text-2xl font-bold text-chart-tsb">{currentPMC.tsb.toFixed(0)}</p>
              </div>
            </div>
          ) : (
            <div className="flex gap-6 mt-4">
              <div>
                <span className="text-muted-foreground text-sm">CTL</span>
                <p className="text-metric">0 <span className="text-sm font-normal text-muted-foreground">→ 0.0%</span></p>
              </div>
              <div>
                <span className="text-muted-foreground text-sm">ATL</span>
                <p className="text-metric">0</p>
              </div>
              <div>
                <span className="text-muted-foreground text-sm">TSB</span>
                <p className="text-metric">0</p>
              </div>
            </div>
          )}
        </div>

        {/* Weekly Summary */}
        <div className="bg-card rounded-xl border border-border p-6 card-hover">
          <h2 className="text-card-title mb-4">This Week</h2>
          {weeklySummary.thisWeek.count === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-center">
              <svg className="w-16 h-16 text-muted-foreground/50 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-muted-foreground mb-1">No rides this week yet</p>
              <p className="text-muted-foreground/70 text-sm">Time to get out there!</p>
              <button 
                onClick={() => navigate("/activities")}
                className="mt-4 text-primary hover:text-primary/80 text-sm font-medium transition-fast"
              >
                Upload a ride →
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Rides</span>
                <span className="text-lg font-semibold text-foreground">{weeklySummary.thisWeek.count}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Time</span>
                <div className="text-right">
                  <span className="text-lg font-semibold text-foreground">{formatDuration(weeklySummary.thisWeek.duration)}</span>
                  {weeklySummary.lastWeek.duration > 0 && (
                    <span className={`ml-2 text-xs ${weeklySummary.thisWeek.duration >= weeklySummary.lastWeek.duration ? "text-success" : "text-destructive"}`}>
                      vs {formatDuration(weeklySummary.lastWeek.duration)}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">TSS</span>
                <div className="text-right">
                  <span className="text-lg font-semibold text-foreground">{Math.round(weeklySummary.thisWeek.tss)}</span>
                  {weeklySummary.lastWeek.tss > 0 && (
                    <span className={`ml-2 text-xs ${weeklySummary.thisWeek.tss >= weeklySummary.lastWeek.tss ? "text-success" : "text-destructive"}`}>
                      vs {Math.round(weeklySummary.lastWeek.tss)}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Distance</span>
                <span className="text-lg font-semibold text-foreground">{formatDistance(weeklySummary.thisWeek.distance)}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recent Activities - Card Grid */}
      <div className="bg-card rounded-xl border border-border p-6 mb-10">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-card-title">Recent Activities</h2>
            <p className="text-body-secondary mt-1">Your latest rides and workouts</p>
          </div>
          <button 
            onClick={() => navigate("/activities")}
            className="text-primary hover:text-primary/80 text-sm font-medium flex items-center gap-1 transition-fast"
          >
            View all
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
        
        {recentActivities.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {recentActivities.map(activity => (
              <div 
                key={activity.id}
                className="bg-muted/30 rounded-xl border border-border overflow-hidden cursor-pointer card-hover group"
                onClick={() => navigate(`/activities/${activity.id}`)}
              >
                {/* Map thumbnail */}
                <div className="relative h-40">
                  <PolylineMap 
                    polyline={activity.map_polyline} 
                    className="w-full h-full opacity-80 group-hover:opacity-100 transition-fast" 
                    showMarkers={true}
                  />
                  {/* Breakthrough badge overlay */}
                  {activity.is_breakthrough && (
                    <div className="absolute top-3 right-3">
                      <span className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium bg-warning/20 text-warning rounded-full">
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        Breakthrough
                      </span>
                    </div>
                  )}
                  {/* Relative time badge */}
                  <div className="absolute bottom-3 left-3">
                    <span className="px-3 py-1 text-xs font-medium text-white bg-black/60 backdrop-blur rounded-full">
                      {formatRelativeTime(activity.started_at)}
                    </span>
                  </div>
                </div>
                
                {/* Activity info */}
                <div className="p-4">
                  {/* Title */}
                  <h3 className="font-semibold text-foreground truncate mb-1">
                    {activity.title || formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: "long", month: "short", day: "numeric" })}
                  </h3>
                  
                  {/* Date */}
                  <p className="text-body-secondary mb-3">
                    {formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: "short", month: "short", day: "numeric" })}
                  </p>
                  
                  {/* Metrics grid - 3 columns */}
                  <div className="grid grid-cols-3 gap-2 text-xs mb-3">
                    <div>
                      <p className="text-muted-foreground">{formatDistance(activity.total_distance_m)}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">{formatDuration(activity.moving_time_s)}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">{formatElevation(activity.elevation_gain_m)}</p>
                    </div>
                  </div>
                  
                  {/* Secondary metrics row */}
                  <div className="flex items-center gap-3 pt-3 border-t border-border text-xs">
                    {activity.avg_power_w && (
                      <div>
                        <span className="font-semibold text-foreground">{activity.avg_power_w}</span>{" "}
                        <span className="text-muted-foreground">W</span>
                      </div>
                    )}
                    {activity.avg_hr_bpm && (
                      <div>
                        <span className="font-semibold text-foreground">{activity.avg_hr_bpm}</span>{" "}
                        <span className="text-muted-foreground">bpm</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-muted/30 rounded-xl p-8 text-center">
            <p className="text-muted-foreground">No activities yet. Upload a FIT file to get started.</p>
          </div>
        )}
      </div>

      {/* What's Notable Section */}
      {(recentBreakthroughs.length > 0 || notablePRs.length > 0) && (
        <div className="bg-card rounded-xl border border-border p-6 mb-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-foreground">What's Notable</h2>
            <button 
              onClick={() => navigate("/records")}
              className="text-primary hover:text-primary/80 text-sm font-medium transition-fast"
            >
              All records →
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Breakthroughs */}
            {recentBreakthroughs.length > 0 && (
              <div>
                <h3 className="text-section-heading text-warning mb-3 flex items-center gap-2">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  Recent Breakthroughs
                </h3>
                <div className="space-y-2">
                  {recentBreakthroughs.map(activity => (
                    <div 
                      key={activity.id}
                      className="bg-muted/50 rounded-lg p-4 cursor-pointer hover:bg-muted transition-fast"
                      onClick={() => navigate(`/activities/${activity.id}`)}
                    >
                      <p className="font-medium text-foreground">
                        {activity.title || formatActivityDate(activity.started_at, activity.utc_offset_minutes, { month: "short", day: "numeric" })}
                      </p>
                      <p className="text-muted-foreground text-sm">
                        {formatActivityDate(activity.started_at, activity.utc_offset_minutes, { month: "short", day: "numeric" })}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Lifetime PRs */}
            {notablePRs.length > 0 && (
              <div>
                <h3 className="text-section-heading text-primary mb-3 flex items-center gap-2">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Lifetime PRs
                </h3>
                <div className="space-y-2">
                  {notablePRs.map((pr, i) => (
                    <div 
                      key={i}
                      className="bg-muted/50 rounded-lg p-3 flex justify-between items-center cursor-pointer hover:bg-muted transition-fast"
                      onClick={() => pr.activityId && navigate(`/activities/${pr.activityId}`)}
                    >
                      <span className="text-muted-foreground text-sm">{pr.label}</span>
                      <span className="font-semibold text-foreground">{pr.value}</span>
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
        className="bg-card rounded-xl border border-border p-6 cursor-pointer card-hover"
        onClick={() => navigate("/power-curve")}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Power Curve</h2>
          <span className="text-primary hover:text-primary/80 text-sm font-medium transition-fast">View full →</span>
        </div>
        {powerCurve.length > 0 ? (
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
        ) : (
          <div className="h-40 bg-muted/30 rounded-lg flex flex-col items-center justify-center text-center relative overflow-hidden">
            {/* Decorative gradient area */}
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
        )}
        {powerCurve.length > 0 && (
          <div className="grid grid-cols-4 gap-4 mt-4">
            <div>
              <p className="text-muted-foreground text-xs mb-1">5s</p>
              <p className="text-lg font-semibold text-foreground">{powerCurve.find(p => p.duration_seconds === 5)?.watts || "—"}<span className="text-sm font-normal text-muted-foreground ml-1">W</span></p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">1m</p>
              <p className="text-lg font-semibold text-foreground">{powerCurve.find(p => p.duration_seconds === 60)?.watts || "—"}<span className="text-sm font-normal text-muted-foreground ml-1">W</span></p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">5m</p>
              <p className="text-lg font-semibold text-foreground">{powerCurve.find(p => p.duration_seconds === 300)?.watts || "—"}<span className="text-sm font-normal text-muted-foreground ml-1">W</span></p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">20m</p>
              <p className="text-lg font-semibold text-foreground">{powerCurve.find(p => p.duration_seconds === 1200)?.watts || "—"}<span className="text-sm font-normal text-muted-foreground ml-1">W</span></p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
