/**
 * Dashboard page - Main overview of training data
 */
import type { JSX } from "react";
import { useState, useEffect, useMemo, useRef } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import type { Activity, PMCPoint, PowerCurvePoint, RecordsResponse, ThresholdEntry, User } from "../api";
import { 
  fetchActivities, 
  fetchPMC, 
  fetchPowerCurve, 
  fetchRecords,
  fetchThresholds,
  fetchMe,
} from "../api";
import { PageHeader } from "../components/PageHeader";
import { Button } from "@/components/ui/button";
import {
  DashboardSkeleton,
  DashboardEmptyState,
  PMCSparkline,
  PeriodSummary,
  FTPCard,
  RecentActivities,
  WhatsNotable,
  PowerCurveThumbnail,
} from "@/components/dashboard";

export function Dashboard(): JSX.Element {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [pmcData, setPmcData] = useState<PMCPoint[]>([]);
  const [powerCurve, setPowerCurve] = useState<PowerCurvePoint[]>([]);
  const [records, setRecords] = useState<RecordsResponse | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [user, setUser] = useState<User | null>(null);
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
      fetchRecords(),
      fetchThresholds().catch(() => []),
      fetchMe().catch(() => null),
    ])

      .then(([acts, pmc, curve, recs, thresh, me]) => {
        setActivities(acts.activities);
        setPmcData(pmc);
        setPowerCurve(curve);
        setRecords(recs);
        setThresholds(thresh);
        setUser(me);
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

  // Previous PMC (7 days ago) for trend calculation
  const previousPMC = pmcData.length > 7 ? pmcData[pmcData.length - 8] : null;
  const ctlTrend = currentPMC && previousPMC 
    ? ((currentPMC.ctl - previousPMC.ctl) / (previousPMC.ctl || 1) * 100)
    : null;

  // Current threshold (most recent)
  const currentThreshold = useMemo(() => {
    if (thresholds.length === 0) return null;
    return thresholds[0];
  }, [thresholds]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (activities.length === 0) {
    return <DashboardEmptyState />;
  }



  return (
    <div className="p-8">
      <PageHeader title="Dashboard" />

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

      {/* Top Row: PMC Sparkline + Period Summary + FTP */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10 items-stretch">
        <PMCSparkline pmcData={pmcData} currentPMC={currentPMC} ctlTrend={ctlTrend} />
        <div className="flex flex-col gap-6">
          <PeriodSummary activities={activities} />
          <FTPCard currentThreshold={currentThreshold} user={user} />
        </div>
      </div>

      <RecentActivities activities={activities} />
      <WhatsNotable activities={activities} records={records} />
      <PowerCurveThumbnail powerCurve={powerCurve} />
    </div>
  );
}
