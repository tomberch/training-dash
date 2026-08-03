import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import type { Activity } from "../api";
import { fetchActivity } from "../api";
import { ActivitySelector } from "../components/ActivitySelector";

export function AnalyzePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activityIdParam = searchParams.get("activity");
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);
  
  // Track if we've already loaded from URL to avoid re-fetching
  const loadedFromUrl = useRef(false);

  // Load activity from URL param on mount
  useEffect(() => {
    if (activityIdParam && !loadedFromUrl.current) {
      const id = parseInt(activityIdParam, 10);
      if (!isNaN(id)) {
        loadedFromUrl.current = true;
        fetchActivity(id)
          .then(setSelectedActivity)
          .catch((e) => {
            console.error("[AnalyzePage] Failed to load activity from URL:", e);
            setSearchParams({});
          });
      }
    }
  }, [activityIdParam, setSearchParams]);

  const handleActivitySelect = (activity: Activity | null) => {
    setSelectedActivity(activity);
    if (activity) {
      setSearchParams({ activity: activity.id.toString() });
    } else {
      setSearchParams({});
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          Analyze
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Deep multi-metric overlay exploration for a single activity.
        </p>

        {/* Activity selector */}
        <div className="mb-6">
          <ActivitySelector
            selectedId={selectedActivity?.id ?? null}
            onSelect={handleActivitySelect}
            label="Select Activity"
            placeholder="Search for an activity..."
          />
        </div>

        {selectedActivity ? (
          <div className="space-y-6">
            {/* Activity header */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {selectedActivity.title || "Untitled Activity"}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {new Date(selectedActivity.started_at).toLocaleDateString(undefined, {
                  weekday: "long",
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </p>
            </div>

            {/* Placeholder for analysis content */}
            <div className="p-8 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 text-center">
              <p className="text-gray-500 dark:text-gray-400">
                Coming soon: Sticky map, multi-metric chart overlays, smoothing controls, and more.
              </p>
            </div>
          </div>
        ) : (
          <div className="p-8 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 text-center">
            <p className="text-gray-500 dark:text-gray-400">
              Select an activity above to begin analysis.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
