import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceArea,
} from "recharts";
import type { Activity, PMCPoint, PowerCurvePoint, Notification, GeoJSONFeatureCollection, RecordsResponse } from "../api";
import { 
  fetchActivities, 
  fetchPMC, 
  fetchPowerCurve, 
  fetchNotifications,
  acceptNotification,
  dismissNotification,
  fetchActivityRecords,
  fetchRecords,
} from "../api";
import { MiniMap } from "../components/MiniMap";

// TSB zone definitions (same as PMC view)
const TSB_ZONES = [
  { name: "Fresh", min: 25, max: 100, color: "#bbf7d0" },
  { name: "Optimal", min: 5, max: 25, color: "#fef08a" },
  { name: "Neutral", min: -10, max: 5, color: "#e5e7eb" },
  { name: "Fatigued", min: -25, max: -10, color: "#fed7aa" },
  { name: "Very Fatigued", min: -100, max: -25, color: "#fecaca" },
];

function getTSBZone(tsb: number) {
  return TSB_ZONES.find(z => tsb >= z.min && tsb < z.max) || TSB_ZONES[4];
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatDistance(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`;
}

export function Dashboard() {
  const navigate = useNavigate();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [pmcData, setPmcData] = useState<PMCPoint[]>([]);
  const [powerCurve, setPowerCurve] = useState<PowerCurvePoint[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [featuredActivityGps, setFeaturedActivityGps] = useState<GeoJSONFeatureCollection | null>(null);
  const [records, setRecords] = useState<RecordsResponse | null>(null);
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
    ])
      .then(([acts, pmc, curve, notifs, recs]) => {
        setActivities(acts.activities);
        setPmcData(pmc);
        setPowerCurve(curve);
        setNotifications(notifs);
        setRecords(recs);
        setLoading(false);
        
        // Fetch GPS data for featured activity (first one)
        if (acts.activities.length > 0) {
          fetchActivityRecords(acts.activities[0].id)
            .then(setFeaturedActivityGps)
            .catch(() => setFeaturedActivityGps(null));
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

  // Featured activity (most recent)
  const featuredActivity = activities.length > 0 ? activities[0] : null;

  // Recent activities (next 4 after featured)
  const recentActivities = activities.slice(1, 5);

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
    const prs: { label: string; value: string; activityId?: number }[] = [];
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
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  // Empty state when no activities
  if (activities.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-indigo-100 dark:bg-indigo-900/30 mb-6">
            <svg className="w-10 h-10 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-3">Welcome to TrainDash</h1>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-md mx-auto">
            Get started by uploading your first activity or connecting to Xert/Garmin to sync automatically.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {/* Step 1: Set thresholds */}
          <div 
            className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 cursor-pointer hover:border-indigo-300 dark:hover:border-indigo-600 transition-colors"
            onClick={() => navigate("/settings")}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-600 text-white text-sm font-bold">1</div>
              <h3 className="font-semibold text-gray-900 dark:text-white">Set Your FTP</h3>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Configure your power thresholds to enable TSS, training load, and performance tracking.
            </p>
          </div>

          {/* Step 2: Connect or upload */}
          <div 
            className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 cursor-pointer hover:border-indigo-300 dark:hover:border-indigo-600 transition-colors"
            onClick={() => navigate("/settings")}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-600 text-white text-sm font-bold">2</div>
              <h3 className="font-semibold text-gray-900 dark:text-white">Connect Accounts</h3>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Link your Xert or Garmin account to automatically sync your rides.
            </p>
          </div>

          {/* Step 3: Upload manually */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-gray-400 dark:bg-gray-600 text-white text-sm font-bold">or</div>
              <h3 className="font-semibold text-gray-900 dark:text-white">Upload FIT Files</h3>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Use the "Upload FIT" button in the header to manually upload activity files.
            </p>
          </div>
        </div>

        {/* Quick stats preview */}
        <div className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl border border-indigo-100 dark:border-indigo-800 p-6">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">What you'll see here</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span>Performance chart</span>
            </div>
            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              <span>Power curve</span>
            </div>
            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Weekly summary</span>
            </div>
            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Dashboard</h1>

      {/* Notifications Banner */}
      {notifications.length > 0 && (
        <div className="mb-6 space-y-2">
          {notifications.map(notif => (
            <div 
              key={notif.id}
              className="flex items-center justify-between p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg"
            >
              <div className="flex items-center gap-3">
                <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm text-amber-800 dark:text-amber-200">{notif.message}</span>
              </div>
              <div className="flex items-center gap-2">
                {notif.payload?.suggested_ftp && (
                  <button
                    onClick={() => handleAcceptNotification(notif.id)}
                    className="px-3 py-1 text-xs font-medium text-white bg-amber-600 hover:bg-amber-700 rounded-lg transition-colors"
                  >
                    Apply {notif.payload.suggested_ftp}W
                  </button>
                )}
                <button
                  onClick={() => handleDismissNotification(notif.id)}
                  className="px-3 py-1 text-xs font-medium text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/40 rounded-lg transition-colors"
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
          className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 cursor-pointer hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors"
          onClick={() => navigate("/pmc")}
        >
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">Performance Management</h2>
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
            <div className="h-40 flex items-center justify-center text-gray-400 text-sm">
              No data available
            </div>
          )}
          
          {currentPMC && (
            <div className="flex gap-6 mt-2 text-sm">
              <div>
                <span className="text-gray-500 dark:text-gray-400">CTL </span>
                <span className="font-medium text-blue-600">{currentPMC.ctl.toFixed(0)}</span>
                {ctlTrend !== null && (
                  <span className={`ml-1 text-xs ${ctlTrend > 0 ? "text-green-600" : ctlTrend < 0 ? "text-red-600" : "text-gray-500"}`}>
                    {ctlTrend > 0 ? "↑" : ctlTrend < 0 ? "↓" : "→"}{Math.abs(ctlTrend).toFixed(1)}%
                  </span>
                )}
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">ATL </span>
                <span className="font-medium text-pink-600">{currentPMC.atl.toFixed(0)}</span>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">TSB </span>
                <span className="font-medium text-amber-600">{currentPMC.tsb.toFixed(0)}</span>
              </div>
            </div>
          )}
        </div>

        {/* Weekly Summary */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">This Week</h2>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Rides</span>
              <span className="font-medium text-gray-900 dark:text-white">{weeklySummary.thisWeek.count}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Time</span>
              <div className="text-right">
                <span className="font-medium text-gray-900 dark:text-white">{formatDuration(weeklySummary.thisWeek.duration)}</span>
                {weeklySummary.lastWeek.duration > 0 && (
                  <span className={`ml-2 text-xs ${weeklySummary.thisWeek.duration >= weeklySummary.lastWeek.duration ? "text-green-600" : "text-red-600"}`}>
                    vs {formatDuration(weeklySummary.lastWeek.duration)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">TSS</span>
              <div className="text-right">
                <span className="font-medium text-gray-900 dark:text-white">{Math.round(weeklySummary.thisWeek.tss)}</span>
                {weeklySummary.lastWeek.tss > 0 && (
                  <span className={`ml-2 text-xs ${weeklySummary.thisWeek.tss >= weeklySummary.lastWeek.tss ? "text-green-600" : "text-red-600"}`}>
                    vs {Math.round(weeklySummary.lastWeek.tss)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Distance</span>
              <span className="font-medium text-gray-900 dark:text-white">{formatDistance(weeklySummary.thisWeek.distance)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Middle Row: Featured Activity + Recent Activities */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Featured Activity */}
        {featuredActivity ? (
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 cursor-pointer hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors"
            onClick={() => navigate(`/activities/${featuredActivity.id}`)}
          >
            <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">Latest Activity</h2>
            
            {/* Mini-map */}
            <MiniMap geojson={featuredActivityGps} className="h-32 mb-3" />
            
            <div className="flex items-start justify-between">
              <div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {featuredActivity.title || new Date(featuredActivity.started_at).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {featuredActivity.title && new Date(featuredActivity.started_at).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
                  {featuredActivity.title && " • "}
                  {formatDistance(featuredActivity.total_distance_m)} • {formatDuration(featuredActivity.moving_time_s)}
                </div>
              </div>
              {featuredActivity.is_breakthrough && (
                <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-amber-800 bg-amber-100 dark:text-amber-200 dark:bg-amber-900/50 rounded-full">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  Breakthrough
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-4 mt-4">
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Avg Power</div>
                <div className="text-sm font-medium text-gray-900 dark:text-white">
                  {featuredActivity.avg_power_w ? `${featuredActivity.avg_power_w} W` : "—"}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400">TSS</div>
                <div className="text-sm font-medium text-gray-900 dark:text-white">
                  {featuredActivity.tss ? Math.round(featuredActivity.tss) : "—"}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Avg HR</div>
                <div className="text-sm font-medium text-gray-900 dark:text-white">
                  {featuredActivity.avg_hr_bpm ? `${featuredActivity.avg_hr_bpm} bpm` : "—"}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">Latest Activity</h2>
            <div className="text-center text-gray-400 py-8">No activities yet</div>
          </div>
        )}

        {/* Recent Activities */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">Recent Activities</h2>
            <button 
              onClick={() => navigate("/activities")}
              className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              View all
            </button>
          </div>
          {recentActivities.length > 0 ? (
            <div className="space-y-2">
              {recentActivities.map(activity => (
                <div 
                  key={activity.id}
                  className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition-colors"
                  onClick={() => navigate(`/activities/${activity.id}`)}
                >
                  <div className="flex items-center gap-3">
                    <div className="text-sm">
                      <div className="font-medium text-gray-900 dark:text-white">
                        {activity.title || new Date(activity.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {activity.title && new Date(activity.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        {activity.title && " • "}
                        {formatDistance(activity.total_distance_m)}
                      </div>
                    </div>
                  </div>
                  <div className="text-right text-sm">
                    <div className="text-gray-900 dark:text-white">{formatDuration(activity.moving_time_s)}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {activity.tss ? `${Math.round(activity.tss)} TSS` : ""}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-400 py-4 text-sm">No recent activities</div>
          )}
        </div>
      </div>

      {/* What's Notable Section */}
      {(recentBreakthroughs.length > 0 || notablePRs.length > 0) && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">What's Notable</h2>
            <button 
              onClick={() => navigate("/records")}
              className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              All records
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Breakthroughs */}
            {recentBreakthroughs.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wide mb-2 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  Recent Breakthroughs
                </h3>
                <div className="space-y-2">
                  {recentBreakthroughs.map(activity => (
                    <div 
                      key={activity.id}
                      className="flex items-center justify-between p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors"
                      onClick={() => navigate(`/activities/${activity.id}`)}
                    >
                      <div className="text-sm">
                        <div className="font-medium text-gray-900 dark:text-white">
                          {activity.title || new Date(activity.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {new Date(activity.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        </div>
                      </div>
                      <span className="text-xs font-medium text-amber-700 dark:text-amber-300">
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
                <h3 className="text-xs font-medium text-indigo-600 dark:text-indigo-400 uppercase tracking-wide mb-2 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                  </svg>
                  Lifetime PRs
                </h3>
                <div className="space-y-2">
                  {notablePRs.map((pr, i) => (
                    <div 
                      key={i}
                      className="flex items-center justify-between p-2 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-900/30 transition-colors"
                      onClick={() => pr.activityId && navigate(`/activities/${pr.activityId}`)}
                    >
                      <span className="text-sm text-gray-600 dark:text-gray-400">{pr.label}</span>
                      <span className="text-sm font-medium text-gray-900 dark:text-white">{pr.value}</span>
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
        className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 cursor-pointer hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors"
        onClick={() => navigate("/power-curve")}
      >
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">Power Curve</h2>
          <span className="text-xs text-indigo-600 dark:text-indigo-400">View full →</span>
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
          <div className="h-32 flex items-center justify-center text-gray-400 text-sm">
            No power data available
          </div>
        )}
        {powerCurve.length > 0 && (
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
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
