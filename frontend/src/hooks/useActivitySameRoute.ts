import { useState, useEffect } from "react";
import type { SameRouteResponse } from "../api";
import { ApiError, fetchSameRouteActivities } from "../api";

export interface UseActivitySameRouteResult {
  loading: boolean;
  error: Error | ApiError | null;
  sameRoute: SameRouteResponse | null;
}

/**
 * Hook for same-route activities - loaded lazily (for Compare button).
 * Provides list of activities on the same route for comparison.
 */
export function useActivitySameRoute(activityId: string): UseActivitySameRouteResult {
  const [sameRoute, setSameRoute] = useState<SameRouteResponse | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetchSameRouteActivities(activityId)
      .then((data) => setSameRoute(data))
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, [activityId]);

  return {
    loading,
    error,
    sameRoute,
  };
}
