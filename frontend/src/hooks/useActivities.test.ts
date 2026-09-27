import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useActivities, invalidateActivitiesCache } from "./useActivities";
import type { Activity } from "../api";

// Mock the API module
vi.mock("../api", () => ({
  fetchActivities: vi.fn(),
}));

import { fetchActivities } from "../api";

const mockFetchActivities = vi.mocked(fetchActivities);

// Factory to create a complete Activity object
function createMockActivity(overrides: Partial<Activity> = {}): Activity {
  return {
    id: "activity-1",
    title: "Morning Ride",
    title_source: "auto",
    started_at: "2024-03-15T10:00:00",
    total_distance_m: 40000,
    moving_time_s: 3600,
    timer_time_s: null,
    elapsed_time_s: 3700,
    elevation_gain_m: 200,
    elevation_loss_m: null,
    min_altitude_m: null,
    max_altitude_m: null,
    max_grade_pct: null,
    avg_speed_mps: 8.0,
    avg_speed_moving_mps: null,
    max_speed_mps: 12.0,
    avg_hr_bpm: 140,
    max_hr_bpm: 160,
    avg_power_w: 240,
    max_power_w: null,
    np_power_w: null,
    intensity_factor: null,
    tss: null,
    training_load: null,
    power_zone_times: null,
    hr_zone_times: null,
    wbal_min_joules: null,
    wbal_min_pct: null,
    power_source: null,
    power_confidence: null,
    calories: null,
    calories_source: null,
    avg_cadence_rpm: null,
    avg_cadence_pedaling_rpm: null,
    max_cadence_rpm: null,
    avg_temperature_c: null,
    min_temperature_c: null,
    max_temperature_c: null,
    peaks: [],
    is_breakthrough: false,
    map_polyline: null,
    utc_offset_minutes: null,
    activity_type: "road",
    bike_id: null,
    bike: null,
    estimated_cda: null,
    estimated_crr: null,
    aero_confidence: null,
    weather_status: null,
    ...overrides,
  };
}

const mockActivities: Activity[] = [
  createMockActivity({ id: "activity-1", title: "Morning Ride" }),
  createMockActivity({
    id: "activity-2",
    title: "Afternoon Ride",
    started_at: "2024-03-14T14:00:00",
    total_distance_m: 30000,
    moving_time_s: 2700,
    elapsed_time_s: 2800,
    elevation_gain_m: 150,
    avg_speed_mps: 7.5,
    max_speed_mps: 11.0,
    avg_hr_bpm: 135,
    max_hr_bpm: 155,
    avg_power_w: 220,
  }),
];

describe("useActivities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear the cache between tests
    invalidateActivitiesCache();
    mockFetchActivities.mockResolvedValue({
      activities: mockActivities,
      pagination: {
        total: 2,
        page: 1,
        per_page: 100,
        total_pages: 1,
      },
    });
  });

  describe("initial fetch", () => {
    it("starts in loading state", () => {
      const { result } = renderHook(() => useActivities());
      expect(result.current.loading).toBe(true);
    });

    it("fetches activities on mount", async () => {
      const { result } = renderHook(() => useActivities());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(mockFetchActivities).toHaveBeenCalledWith(1, 100);
      expect(result.current.activities).toEqual(mockActivities);
    });

    it("respects maxActivities parameter", async () => {
      const { result } = renderHook(() => useActivities(50));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(mockFetchActivities).toHaveBeenCalledWith(1, 50);
    });
  });

  describe("error handling", () => {
    it("sets error state on fetch failure", async () => {
      mockFetchActivities.mockRejectedValue(new Error("Network error"));

      const { result } = renderHook(() => useActivities());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toBe("Network error");
      expect(result.current.activities).toEqual([]);
    });

    it("uses generic message for non-Error exceptions", async () => {
      mockFetchActivities.mockRejectedValue("string error");

      const { result } = renderHook(() => useActivities());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toBe("Failed to load activities");
    });
  });

  describe("caching", () => {
    it("uses cached data for subsequent hooks", async () => {
      // First hook fetch
      const { result: result1 } = renderHook(() => useActivities());
      await waitFor(() => {
        expect(result1.current.loading).toBe(false);
      });
      expect(mockFetchActivities).toHaveBeenCalledTimes(1);

      // Second hook should use cache
      const { result: result2 } = renderHook(() => useActivities());

      // Should immediately have data without loading
      expect(result2.current.activities).toEqual(mockActivities);
      // Should not fetch again
      expect(mockFetchActivities).toHaveBeenCalledTimes(1);
    });

    it("invalidateActivitiesCache clears the cache", async () => {
      // First hook fetch
      const { result: result1 } = renderHook(() => useActivities());
      await waitFor(() => {
        expect(result1.current.loading).toBe(false);
      });
      expect(mockFetchActivities).toHaveBeenCalledTimes(1);

      // Invalidate cache
      invalidateActivitiesCache();

      // New hook should fetch again
      const { result: result2 } = renderHook(() => useActivities());
      await waitFor(() => {
        expect(result2.current.loading).toBe(false);
      });
      expect(mockFetchActivities).toHaveBeenCalledTimes(2);
    });
  });

  describe("refetch", () => {
    it("provides refetch function that forces new fetch", async () => {
      const { result } = renderHook(() => useActivities());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(mockFetchActivities).toHaveBeenCalledTimes(1);

      // Update mock to return different data
      const newActivities = [createMockActivity({ id: "activity-1", title: "Updated Ride" })];
      mockFetchActivities.mockResolvedValue({
        activities: newActivities,
        pagination: {
          total: 1,
          page: 1,
          per_page: 100,
          total_pages: 1,
        },
      });

      // Call refetch
      act(() => {
        result.current.refetch();
      });

      await waitFor(() => {
        expect(result.current.activities[0].title).toBe("Updated Ride");
      });

      expect(mockFetchActivities).toHaveBeenCalledTimes(2);
    });

    it("sets loading state during refetch", async () => {
      const { result } = renderHook(() => useActivities());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Create a delayed promise
      let resolvePromise: (value: Awaited<ReturnType<typeof fetchActivities>>) => void;
      mockFetchActivities.mockImplementation(
        () =>
          new Promise((resolve) => {
            resolvePromise = resolve;
          })
      );

      // Call refetch
      act(() => {
        result.current.refetch();
      });

      expect(result.current.loading).toBe(true);

      // Resolve the promise
      act(() => {
        resolvePromise!({
          activities: mockActivities,
          pagination: {
            total: 2,
            page: 1,
            per_page: 100,
            total_pages: 1,
          },
        });
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
    });
  });

  describe("return values", () => {
    it("returns all expected properties", async () => {
      const { result } = renderHook(() => useActivities());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current).toHaveProperty("activities");
      expect(result.current).toHaveProperty("loading");
      expect(result.current).toHaveProperty("error");
      expect(result.current).toHaveProperty("refetch");
      expect(typeof result.current.refetch).toBe("function");
    });

    it("returns null error when successful", async () => {
      const { result } = renderHook(() => useActivities());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toBeNull();
    });
  });
});
