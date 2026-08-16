/**
 * EventTourMap - Displays a resizable map showing all activities in an event.
 * For multi-day events, each day is shown in a different color with a legend.
 */

import { useMemo } from "react";
import { ResizableMap } from "./ResizableMap";
import { useResizableMap } from "@/hooks/useResizableMap";
import { decodePolyline } from "./PolylineMap";
import { DAY_COLORS } from "@/constants";
import type { JournalEntry, JournalEntryActivity } from "@/api/events";

interface DayRoute {
  dayIndex: number;
  date: string;
  positions: [number, number][];
  color: string;
}

interface EventTourMapProps {
  entries: (JournalEntry & { activities: JournalEntryActivity[] })[];
  isSingleDay: boolean;
}

export function EventTourMap({ entries, isSingleDay }: EventTourMapProps) {
  const { height, isResizing, startResizeHeight } = useResizableMap({
    storageKey: "event-tour-map",
    defaultHeight: 300,
    minHeight: 150,
    maxHeight: 600,
    defaultWidthPercent: 100,
    minWidthPercent: 100,
    maxWidthPercent: 100,
  });

  // Extract polylines from activities, grouped by day
  const { allPositions, dayRoutes } = useMemo(() => {
    const routes: DayRoute[] = [];
    const allPos: [number, number][] = [];

    // Sort entries by date
    const sortedEntries = [...entries].sort(
      (a, b) => new Date(a.entry_date).getTime() - new Date(b.entry_date).getTime()
    );

    sortedEntries.forEach((entry, dayIndex) => {
      const dayPositions: [number, number][] = [];

      // Get all activities for this day
      const sortedActivities = [...entry.activities].sort((a, b) => {
        const aTime = a.activity?.started_at ? new Date(a.activity.started_at).getTime() : 0;
        const bTime = b.activity?.started_at ? new Date(b.activity.started_at).getTime() : 0;
        return aTime - bTime;
      });

      for (const activityLink of sortedActivities) {
        const polyline = activityLink.activity?.map_polyline;
        if (polyline) {
          const decoded = decodePolyline(polyline);
          dayPositions.push(...decoded);
          allPos.push(...decoded);
        }
      }

      if (dayPositions.length > 0) {
        routes.push({
          dayIndex: dayIndex + 1,
          date: entry.entry_date,
          positions: dayPositions,
          color: DAY_COLORS[dayIndex % DAY_COLORS.length],
        });
      }
    });

    return { allPositions: allPos, dayRoutes: routes };
  }, [entries]);

  // Don't render if no GPS data
  if (allPositions.length === 0) {
    return null;
  }

  // For single-day events, just show a simple map without day coloring
  if (isSingleDay) {
    return (
      <section className="mb-8">
        <h2 className="text-card-title mb-3">Route</h2>
        <ResizableMap
          positions={allPositions}
          height={height}
          onResizeStart={startResizeHeight}
          isResizing={isResizing}
          showResizeHandle={true}
        />
      </section>
    );
  }

  // For multi-day events, use colored segments and show legend
  const coloredSegments = dayRoutes.map((route) => ({
    positions: route.positions,
    color: route.color,
  }));

  return (
    <section className="mb-8">
      <h2 className="text-card-title mb-3">Tour Route</h2>
      <div className="relative">
        <ResizableMap
          positions={allPositions}
          coloredSegments={coloredSegments}
          height={height}
          onResizeStart={startResizeHeight}
          isResizing={isResizing}
          showResizeHandle={true}
        />
        {/* Day Legend - same style as ActivityDetail power zone legend */}
        <div className="absolute bottom-6 left-12 z-[1000] bg-card/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-border shadow-lg">
          <div className="flex items-center gap-3 text-xs flex-wrap">
            {dayRoutes.map((route) => (
              <div key={route.dayIndex} className="flex items-center gap-1.5">
                <span
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: route.color }}
                />
                <span className="text-foreground">
                  Day {route.dayIndex}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
