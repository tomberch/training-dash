import { useState, useEffect } from "react";
import type { WbalResponse } from "../api";
import { ApiError, fetchActivityWbal } from "../api";

export interface UseActivityWbalResult {
  loading: boolean;
  error: Error | ApiError | null;
  wbalData: WbalResponse | null;
}

/**
 * Hook for W'bal data - loaded lazily (below the fold).
 * Provides W'bal time series for the W'bal chart.
 */
export function useActivityWbal(activityId: string): UseActivityWbalResult {
  const [wbalData, setWbalData] = useState<WbalResponse | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setWbalData(null);

    fetchActivityWbal(activityId)
      .then((data) => setWbalData(data))
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, [activityId]);

  return {
    loading,
    error,
    wbalData,
  };
}
