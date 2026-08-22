import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useActivityDetail } from "./useActivityDetail";

vi.mock("../api", () => ({
  fetchActivity: vi.fn(),
  fetchActivityRecords: vi.fn(),
  fetchSameRouteActivities: vi.fn(),
  fetchActivityWbal: vi.fn(),
  fetchThresholds: vi.fn(),
  updateActivityTitle: vi.fn(),
  generateActivityTitle: vi.fn(),
}));

import {
  fetchActivity,
  fetchActivityRecords,
  fetchSameRouteActivities,
  fetchActivityWbal,
  fetchThresholds,
  updateActivityTitle,
  generateActivityTitle,
} from "../api";

const mockFetchActivity = vi.mocked(fetchActivity);
const mockFetchActivityRecords = vi.mocked(fetchActivityRecords);
const mockFetchSameRouteActivities = vi.mocked(fetchSameRouteActivities);
const mockFetchActivityWbal = vi.mocked(fetchActivityWbal);
const mockFetchThresholds = vi.mocked(fetchThresholds);
const mockUpdateActivityTitle = vi.mocked(updateActivityTitle);
const mockGenerateActivityTitle = vi.mocked(generateActivityTitle);

const mockActivity = {
  id: "test-uuid-1",
  title: "Morning Ride",
  title_source: "auto" as const,
  started_at: "2024-03-15T10:00:00",
  total_distance_m: 40000,
  moving_time_s: 3600,
  elapsed_time_s: 3700,
  elevation_gain_m: 200,
  avg_speed_mps: 8.0,
  avg_hr_bpm: 140,
  avg_power_w: 240,
  max_speed_mps: 12.0,
  max_hr_bpm: 160,
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
  peaks: [],
  is_breakthrough: false,
  map_polyline: null,
  utc_offset_minutes: null,
  activity_type: null,
  bike_id: null,
  bike: null,
  estimated_cda: null,
  estimated_crr: null,
  aero_confidence: null,
  weather_status: null,
  effective_ftp: null,
  effective_lthr: null,
};

const mockGeojson = {
  type: "FeatureCollection" as const,
  activity_id: "test-uuid-1",
  features: [
    {
      type: "Feature" as const,
      geometry: { type: "Point", coordinates: [8.5417, 47.3769] },
      properties: {
        timestamp: "2024-03-15T10:00:00",
        distance_m: 0,
        hr_bpm: 120,
        power_w: 200,
        speed_mps: 8.0,
        altitude_m: 500,
        cadence_rpm: 80,
      },
    },
    {
      type: "Feature" as const,
      geometry: { type: "Point", coordinates: [8.5418, 47.377] },
      properties: {
        timestamp: "2024-03-15T10:00:10",
        distance_m: 100,
        hr_bpm: 121,
        power_w: 201,
        speed_mps: 8.01,
        altitude_m: 501,
        cadence_rpm: 81,
      },
    },
  ],
};

const mockSameRoute = {
  route_id: 1,
  activities: [
    { ...mockActivity, id: "test-uuid-2", started_at: "2024-03-10T08:00:00" },
  ],
};

const mockWbalData = {
  wbal_series: [],
  w_prime_joules: 20000,
  ftp_watts: 250,
  wbal_min_joules: null,
  wbal_min_pct: null,
};

const mockThresholds = [
  { effective_date: "2024-01-01", ftp_watts: 240, lthr_bpm: 160, hrmax_bpm: 185 },
];

describe("useActivityDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchActivity.mockResolvedValue(mockActivity);
    mockFetchActivityRecords.mockResolvedValue(mockGeojson);
    mockFetchSameRouteActivities.mockResolvedValue(mockSameRoute);
    mockFetchActivityWbal.mockResolvedValue(mockWbalData);
    mockFetchThresholds.mockResolvedValue(mockThresholds);
  });

  it("fetches all data in parallel on mount", async () => {
    renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(mockFetchActivity).toHaveBeenCalledWith("test-uuid-1");
      expect(mockFetchActivityRecords).toHaveBeenCalledWith("test-uuid-1");
      expect(mockFetchSameRouteActivities).toHaveBeenCalledWith("test-uuid-1");
      expect(mockFetchActivityWbal).toHaveBeenCalledWith("test-uuid-1");
      expect(mockFetchThresholds).toHaveBeenCalled();
    });
  });

  it("returns loading state initially", () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));
    expect(result.current.loading).toBe(true);
  });

  it("returns activity data after loading", async () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.activity).toEqual(mockActivity);
    expect(result.current.geojson).toEqual(mockGeojson);
    expect(result.current.sameRoute).toEqual(mockSameRoute);
    expect(result.current.wbalData).toEqual(mockWbalData);
  });

  it("derives positions from geojson", async () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.positions).toHaveLength(2);
    expect(result.current.positions[0]).toEqual([47.3769, 8.5417]);
  });

  it("derives records from geojson", async () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.records).toHaveLength(2);
    expect(result.current.records[0]).toEqual({
      distance_m: 0,
      hr_bpm: 120,
      power_w: 200,
      speed_mps: 8.0,
      altitude_m: 500,
    });
  });

  it("uses FTP from wbalData when available", async () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.ftpWatts).toBe(250); // from wbalData, not thresholds
  });

  it("falls back to threshold FTP when wbalData has no FTP", async () => {
    mockFetchActivityWbal.mockResolvedValue({
      ...mockWbalData,
      ftp_watts: null,
    });

    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.ftpWatts).toBe(240); // from thresholds
  });

  it("toggles axis mode for a chart", async () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.axisModes.speed).toBe("time");
    
    act(() => {
      result.current.toggleAxis("speed");
    });
    expect(result.current.axisModes.speed).toBe("distance");
    
    act(() => {
      result.current.toggleAxis("speed");
    });
    expect(result.current.axisModes.speed).toBe("time");
  });

  it("saves title via API", async () => {
    mockUpdateActivityTitle.mockResolvedValue({
      ...mockActivity,
      title: "New Title",
      title_source: "manual" as const,
    });

    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.saveTitle("New Title");
    });

    expect(mockUpdateActivityTitle).toHaveBeenCalledWith("test-uuid-1", "New Title");
    expect(result.current.activity?.title).toBe("New Title");
  });

  it("generates title via API", async () => {
    mockGenerateActivityTitle.mockResolvedValue({
      ...mockActivity,
      title: "Generated Title",
      title_source: "auto" as const,
    });

    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.generateTitle();
    });

    expect(mockGenerateActivityTitle).toHaveBeenCalledWith("test-uuid-1");
    expect(result.current.activity?.title).toBe("Generated Title");
  });

  it("sets error state on fetch failure", async () => {
    const error = new Error("Network error");
    mockFetchActivity.mockRejectedValue(error);

    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toEqual(error);
  });

  it("finds position by elapsed time", async () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // First point at elapsed 0
    const pos = result.current.findPositionByElapsed(0);
    expect(pos).toEqual([47.3769, 8.5417]);
  });

  it("finds position by distance", async () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Second point at distance 100m
    const pos = result.current.findPositionByDistance(100);
    expect(pos).toEqual([47.377, 8.5418]);
  });

  it("manages expanded chart state", async () => {
    const { result } = renderHook(() => useActivityDetail("test-uuid-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.expandedChart).toBeNull();
    
    act(() => {
      result.current.setExpandedChart("power");
    });
    expect(result.current.expandedChart).toBe("power");
    
    act(() => {
      result.current.setExpandedChart(null);
    });
    expect(result.current.expandedChart).toBeNull();
  });
});
