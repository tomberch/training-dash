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
import type { Activity, PMCPoint, PowerCurvePoint, Notification } from "../api";
import { 
  fetchActivities, 
  fetchPMC, 
  fetchPowerCurve, 
  fetchNotifications,
  acceptNotification,
  dismissNotification,
} from "../api";

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
    ])
      .then(([acts, pmc, curve, notifs]) => {
        setActivities(acts);
        setPmcData(pmc);
        setPowerCurve(curve);
        setNotifications(notifs);
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

  // Featured activity (most recent)
  const featuredActivity = activities.length > 0 ? activities[0] : null;

  // Recent activities (next 4 after featured)
  const recentActivities = activities.slice(1, 5);

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
            <div className="h-24 overflow-hidden">
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
            <div className="h-24 flex items-center justify-center text-gray-400 text-sm">
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
            <div className="flex items-start justify-between">
              <div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {new Date(featuredActivity.started_at).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
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
                        {new Date(activity.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
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
