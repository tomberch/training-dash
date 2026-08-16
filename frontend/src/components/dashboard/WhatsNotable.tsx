/**
 * What's Notable widget - Breakthroughs and Lifetime PRs
 */
import type { JSX } from "react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { Activity, RecordsResponse } from "@/api";
import { formatDistance, formatActivityDate } from "@/format";

interface WhatsNotableProps {
  activities: Activity[];
  records: RecordsResponse | null;
}

export function WhatsNotable({ activities, records }: WhatsNotableProps): JSX.Element | null {
  const navigate = useNavigate();

  const recentBreakthroughs = useMemo(() => {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    return activities
      .filter(a => a.is_breakthrough && new Date(a.started_at) >= thirtyDaysAgo)
      .slice(0, 3);
  }, [activities]);

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



  // Don't render if nothing notable
  if (recentBreakthroughs.length === 0 && notablePRs.length === 0) {
    return null;
  }

  return (
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
        {recentBreakthroughs.length > 0 && (
          <BreakthroughsList breakthroughs={recentBreakthroughs} onActivityClick={(id) => navigate(`/activities/${id}`)} />
        )}
        
        {notablePRs.length > 0 && (
          <LifetimePRsList prs={notablePRs} onActivityClick={(id) => navigate(`/activities/${id}`)} />
        )}
      </div>
    </div>
  );
}

interface BreakthroughsListProps {
  breakthroughs: Activity[];
  onActivityClick: (id: string) => void;
}

function BreakthroughsList({ breakthroughs, onActivityClick }: BreakthroughsListProps): JSX.Element {
  return (
    <div>
      <h3 className="text-section-heading text-warning mb-3 flex items-center gap-2">
        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
        Recent Breakthroughs
      </h3>
      <div className="space-y-2">
        {breakthroughs.map(activity => (
          <div 
            key={activity.id}
            className="bg-muted/50 rounded-lg p-4 cursor-pointer hover:bg-muted transition-fast"
            onClick={() => onActivityClick(activity.id)}
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
  );
}



interface LifetimePRsListProps {
  prs: { label: string; value: string; activityId?: string }[];
  onActivityClick: (id: string) => void;
}

function LifetimePRsList({ prs, onActivityClick }: LifetimePRsListProps): JSX.Element {
  return (
    <div>
      <h3 className="text-section-heading text-primary mb-3 flex items-center gap-2">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Lifetime PRs
      </h3>
      <div className="space-y-2">
        {prs.map((pr, i) => (
          <div 
            key={i}
            className="bg-muted/50 rounded-lg p-3 flex justify-between items-center cursor-pointer hover:bg-muted transition-fast"
            onClick={() => pr.activityId && onActivityClick(pr.activityId)}
          >
            <span className="text-muted-foreground text-sm">{pr.label}</span>
            <span className="font-semibold text-foreground">{pr.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
