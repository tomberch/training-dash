/**
 * Recent Activities grid widget
 */
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import type { Activity } from "@/api";
import { PolylineMap } from "../PolylineMap";
import {
  formatDuration,
  formatDistance,
  formatRelativeTime,
  formatElevation,
  formatActivityDate,
  formatActivityTime,
  activityEndTimeIso,
} from "@/format";

interface RecentActivitiesProps {
  activities: Activity[];
}

export function RecentActivities({ activities }: RecentActivitiesProps): JSX.Element {
  const navigate = useNavigate();
  const recentActivities = activities.slice(0, 6);

  return (
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
            <ActivityCard key={activity.id} activity={activity} onClick={() => navigate(`/activities/${activity.id}`)} />
          ))}
        </div>
      ) : (
        <div className="bg-muted/30 rounded-xl p-8 text-center">
          <p className="text-muted-foreground">No activities yet. Upload a FIT file to get started.</p>
        </div>
      )}
    </div>
  );
}



interface ActivityCardProps {
  activity: Activity;
  onClick: () => void;
}

function ActivityCard({ activity, onClick }: ActivityCardProps): JSX.Element {
  return (
    <div 
      className="bg-muted/30 rounded-xl border border-border overflow-hidden cursor-pointer card-hover group"
      onClick={onClick}
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
            <span className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium bg-warning text-warning-foreground rounded-full shadow-sm">
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
        <h3 className="font-semibold text-foreground truncate mb-1">
          {activity.title || formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: "long", month: "short", day: "numeric" })}
        </h3>
        
        <p className="text-body-secondary mb-3">
          {formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: "short", month: "short", day: "numeric" })}
          {" · "}
          {formatActivityTime(activity.started_at, activity.utc_offset_minutes)}
          {" - "}
          {formatActivityTime(activityEndTimeIso(activity.started_at, activity.elapsed_time_s), activity.utc_offset_minutes)}
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
  );
}
