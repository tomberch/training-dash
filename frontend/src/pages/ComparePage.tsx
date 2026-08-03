import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import type { Activity } from "../api";
import { fetchActivity } from "../api";
import { ActivitySelector } from "../components/ActivitySelector";

export function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const baseIdParam = searchParams.get("base");
  const compareIdParam = searchParams.get("compare");
  
  const [baseActivity, setBaseActivity] = useState<Activity | null>(null);
  const [compareActivity, setCompareActivity] = useState<Activity | null>(null);
  
  // Track if we've already loaded from URL
  const loadedBaseFromUrl = useRef(false);
  const loadedCompareFromUrl = useRef(false);

  // Load activities from URL params on mount
  useEffect(() => {
    if (baseIdParam && !loadedBaseFromUrl.current) {
      const id = parseInt(baseIdParam, 10);
      if (!isNaN(id)) {
        loadedBaseFromUrl.current = true;
        fetchActivity(id)
          .then(setBaseActivity)
          .catch((e) => {
            console.error("[ComparePage] Failed to load base activity from URL:", e);
          });
      }
    }
  }, [baseIdParam]);

  useEffect(() => {
    if (compareIdParam && !loadedCompareFromUrl.current) {
      const id = parseInt(compareIdParam, 10);
      if (!isNaN(id)) {
        loadedCompareFromUrl.current = true;
        fetchActivity(id)
          .then(setCompareActivity)
          .catch((e) => {
            console.error("[ComparePage] Failed to load compare activity from URL:", e);
          });
      }
    }
  }, [compareIdParam]);

  const updateSearchParams = (base: Activity | null, compare: Activity | null) => {
    const params: Record<string, string> = {};
    if (base) params.base = base.id.toString();
    if (compare) params.compare = compare.id.toString();
    setSearchParams(params);
  };

  const handleBaseSelect = (activity: Activity | null) => {
    setBaseActivity(activity);
    updateSearchParams(activity, compareActivity);
  };

  const handleCompareSelect = (activity: Activity | null) => {
    setCompareActivity(activity);
    updateSearchParams(baseActivity, activity);
  };

  const handleSwap = () => {
    const temp = baseActivity;
    setBaseActivity(compareActivity);
    setCompareActivity(temp);
    updateSearchParams(compareActivity, temp);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          Compare
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Compare two rides on the same route, focusing on time/pace differences.
        </p>

        {/* Activity selectors */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <ActivitySelector
            selectedId={baseActivity?.id ?? null}
            onSelect={handleBaseSelect}
            excludeIds={compareActivity ? [compareActivity.id] : []}
            label="Base Activity"
            placeholder="Select the base ride..."
          />
          
          <div className="relative">
            <ActivitySelector
              selectedId={compareActivity?.id ?? null}
              onSelect={handleCompareSelect}
              excludeIds={baseActivity ? [baseActivity.id] : []}
              label="Compare With"
              placeholder="Select ride to compare..."
            />
          </div>
        </div>

        {/* Swap button */}
        {baseActivity && compareActivity && (
          <div className="flex justify-center mb-6">
            <button
              onClick={handleSwap}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
              Swap Activities
            </button>
          </div>
        )}

        {/* Comparison content */}
        {baseActivity && compareActivity ? (
          <div className="space-y-6">
            {/* Activities summary */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <div className="text-xs font-medium text-indigo-600 dark:text-indigo-400 uppercase tracking-wide mb-1">
                  Base
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {baseActivity.title || "Untitled"}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {new Date(baseActivity.started_at).toLocaleDateString()}
                </p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <div className="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wide mb-1">
                  Compare
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {compareActivity.title || "Untitled"}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {new Date(compareActivity.started_at).toLocaleDateString()}
                </p>
              </div>
            </div>

            {/* Placeholder for comparison content */}
            <div className="p-8 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 text-center">
              <p className="text-gray-500 dark:text-gray-400">
                Coming soon: Gap chart, power comparison, stats table, and color-coded map segments.
              </p>
            </div>
          </div>
        ) : (
          <div className="p-8 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 text-center">
            <p className="text-gray-500 dark:text-gray-400">
              {!baseActivity && !compareActivity
                ? "Select two activities above to compare them."
                : !baseActivity
                ? "Select a base activity to compare."
                : "Select an activity to compare with."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
