import { useState, useEffect, useCallback } from "react";
import type { Activity } from "../api";
import { fetchActivities } from "../api";

// Simple in-memory cache for activities
let cachedActivities: Activity[] | null = null;
let cacheTimestamp: number = 0;
const CACHE_TTL_MS = 60_000; // 1 minute cache

interface UseActivitiesResult {
  activities: Activity[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Hook to fetch and cache activities list.
 * Uses a simple in-memory cache to avoid duplicate API calls
 * when multiple components need the activities list.
 */
export function useActivities(maxActivities: number = 100): UseActivitiesResult {
  const [activities, setActivities] = useState<Activity[]>(cachedActivities ?? []);
  const [loading, setLoading] = useState(cachedActivities === null);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (force: boolean = false) => {
    const now = Date.now();
    
    // Use cache if valid and not forcing refresh
    if (!force && cachedActivities && (now - cacheTimestamp) < CACHE_TTL_MS) {
      setActivities(cachedActivities);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      const result = await fetchActivities(1, maxActivities);
      cachedActivities = result.activities;
      cacheTimestamp = now;
      setActivities(result.activities);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load activities";
      setError(message);
      console.error("[useActivities] Failed to fetch activities:", e);
    } finally {
      setLoading(false);
    }
  }, [maxActivities]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData(true);
  }, [fetchData]);

  return { activities, loading, error, refetch };
}

/**
 * Invalidate the activities cache.
 * Call this after creating/deleting activities.
 */
export function invalidateActivitiesCache(): void {
  cachedActivities = null;
  cacheTimestamp = 0;
}
