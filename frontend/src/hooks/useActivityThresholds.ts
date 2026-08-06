import { useState, useEffect, useMemo } from "react";
import type { ThresholdEntry, Activity, WbalResponse } from "../api";
import { ApiError, fetchThresholds } from "../api";

export interface UseActivityThresholdsResult {
  loading: boolean;
  error: Error | ApiError | null;
  thresholds: ThresholdEntry[];
  applicableThreshold: ThresholdEntry | null;
  ftpWatts: number | null;
  lthrBpm: number | null;
}

/**
 * Hook for user thresholds (FTP, LTHR) - shared across activity views.
 * Computes the applicable threshold for the activity date.
 * 
 * @param activity - The activity to find applicable threshold for (null while loading)
 * @param wbalData - Optional W'bal response (may contain more accurate FTP)
 */
export function useActivityThresholds(
  activity: Activity | null,
  wbalData?: WbalResponse | null,
): UseActivityThresholdsResult {
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetchThresholds()
      .then((data) => setThresholds(data))
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, []);

  // Derived: applicable threshold for this activity's date
  const applicableThreshold = useMemo(() => {
    if (!activity || thresholds.length === 0) return null;
    const activityDate = new Date(activity.started_at).toISOString().split("T")[0];
    const applicable = thresholds.find((t) => t.effective_date <= activityDate);
    return applicable ?? thresholds[thresholds.length - 1];
  }, [activity, thresholds]);

  // Threshold values (FTP from wbal preferred over threshold)
  const ftpWatts = wbalData?.ftp_watts ?? applicableThreshold?.ftp_watts ?? null;
  const lthrBpm = applicableThreshold?.lthr_bpm ?? null;

  return {
    loading,
    error,
    thresholds,
    applicableThreshold,
    ftpWatts,
    lthrBpm,
  };
}
