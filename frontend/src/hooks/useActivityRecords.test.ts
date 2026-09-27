import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useActivityRecords } from "./useActivityRecords";

// Mock the API module
vi.mock("../api", () => ({
  fetchActivityRecords: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

import { fetchActivityRecords, ApiError } from "../api";

const mockFetchActivityRecords = vi.mocked(fetchActivityRecords);

const mockGeojson = {
  type: "FeatureCollection" as const,
  activity_id: "test-uuid-1",
  features: [
    {
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [8.5417, 47.3769] },
      properties: {
        timestamp: "2024-03-15T10:00:00Z",
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
      geometry: { type: "Point" as const, coordinates: [8.5418, 47.377] },
      properties: {
        timestamp: "2024-03-15T10:00:10Z",
        distance_m: 100,
        hr_bpm: 125,
        power_w: 210,
        speed_mps: 8.5,
        altitude_m: 505,
        cadence_rpm: 85,
      },
    },
    {
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [8.5420, 47.378] },
      properties: {
        timestamp: "2024-03-15T10:00:20Z",
        distance_m: 200,
        hr_bpm: 130,
        power_w: 220,
        speed_mps: 9.0,
        altitude_m: 510,
        cadence_rpm: 90,
      },
    },
  ],
};

describe("useActivityRecords", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchActivityRecords.mockResolvedValue(mockGeojson);
  });

  describe("initial fetch", () => {
    it("starts in loading state", () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));
      expect(result.current.loading).toBe(true);
    });

    it("fetches records on mount", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(mockFetchActivityRecords).toHaveBeenCalledWith("test-uuid-1");
    });

    it("returns geojson data after loading", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.geojson).toEqual(mockGeojson);
    });

    it("refetches when activityId changes", async () => {
      const { result, rerender } = renderHook(
        ({ id }) => useActivityRecords(id),
        { initialProps: { id: "test-uuid-1" } }
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(mockFetchActivityRecords).toHaveBeenCalledWith("test-uuid-1");

      // Change the activity ID
      rerender({ id: "test-uuid-2" });

      await waitFor(() => {
        expect(mockFetchActivityRecords).toHaveBeenCalledWith("test-uuid-2");
      });
    });
  });

  describe("error handling", () => {
    it("sets error state on fetch failure", async () => {
      const error = new Error("Network error");
      mockFetchActivityRecords.mockRejectedValue(error);

      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toEqual(error);
      expect(result.current.geojson).toBeNull();
    });

    it("handles ApiError", async () => {
      const apiError = new ApiError("Not found", 404);
      mockFetchActivityRecords.mockRejectedValue(apiError);

      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toEqual(apiError);
    });
  });

  describe("derived records", () => {
    it("extracts records from geojson", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.records).toHaveLength(3);
      expect(result.current.records[0]).toEqual({
        distance_m: 0,
        hr_bpm: 120,
        power_w: 200,
        speed_mps: 8.0,
        altitude_m: 500,
      });
      expect(result.current.records[1]).toEqual({
        distance_m: 100,
        hr_bpm: 125,
        power_w: 210,
        speed_mps: 8.5,
        altitude_m: 505,
      });
    });

    it("returns empty records when no geojson", () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));
      // During loading, records should be empty
      expect(result.current.records).toEqual([]);
    });
  });

  describe("derived timestamps", () => {
    it("extracts timestamps from geojson", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.timestamps).toHaveLength(3);
      // Timestamps should be in seconds
      expect(result.current.timestamps[0]).toBe(
        new Date("2024-03-15T10:00:00Z").getTime() / 1000
      );
    });

    it("calculates firstTs correctly", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.firstTs).toBe(result.current.timestamps[0]);
    });

    it("returns 0 for firstTs when no timestamps", () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));
      expect(result.current.firstTs).toBe(0);
    });
  });

  describe("derived positions", () => {
    it("extracts positions from geojson (lat/lon order)", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.positions).toHaveLength(3);
      // GeoJSON is [lon, lat], positions should be [lat, lon]
      expect(result.current.positions[0]).toEqual([47.3769, 8.5417]);
      expect(result.current.positions[1]).toEqual([47.377, 8.5418]);
    });

    it("builds posByDist array", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.posByDist).toHaveLength(3);
      expect(result.current.posByDist[0]).toEqual({
        distance_m: 0,
        pos: [47.3769, 8.5417],
      });
      expect(result.current.posByDist[1]).toEqual({
        distance_m: 100,
        pos: [47.377, 8.5418],
      });
    });

    it("builds posByElapsed array", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.posByElapsed).toHaveLength(3);
      expect(result.current.posByElapsed[0].elapsed).toBe(0);
      expect(result.current.posByElapsed[1].elapsed).toBe(10);
      expect(result.current.posByElapsed[2].elapsed).toBe(20);
    });

    it("filters out features with null geometry", async () => {
      const geojsonWithNull = {
        ...mockGeojson,
        features: [
          ...mockGeojson.features,
          {
            type: "Feature" as const,
            geometry: null,
            properties: {
              timestamp: "2024-03-15T10:00:30Z",
              distance_m: 300,
              hr_bpm: 135,
              power_w: 230,
              speed_mps: 9.5,
              altitude_m: 515,
              cadence_rpm: 95,
            },
          },
        ],
      };
      mockFetchActivityRecords.mockResolvedValue(geojsonWithNull);

      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // positions should only include features with valid geometry
      expect(result.current.positions).toHaveLength(3);
    });
  });

  describe("findPositionByElapsed", () => {
    it("finds nearest position by elapsed time", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Exact match at 0s
      expect(result.current.findPositionByElapsed(0)).toEqual([47.3769, 8.5417]);

      // Exact match at 10s
      expect(result.current.findPositionByElapsed(10)).toEqual([47.377, 8.5418]);

      // Closest to 8s should be 10s point
      expect(result.current.findPositionByElapsed(8)).toEqual([47.377, 8.5418]);

      // Closest to 3s should be 0s point
      expect(result.current.findPositionByElapsed(3)).toEqual([47.3769, 8.5417]);
    });

    it("returns null when no positions available", () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));
      // During loading
      expect(result.current.findPositionByElapsed(0)).toBeNull();
    });
  });

  describe("findPositionByDistance", () => {
    it("finds nearest position by distance", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Exact match at 0m
      expect(result.current.findPositionByDistance(0)).toEqual([47.3769, 8.5417]);

      // Exact match at 100m
      expect(result.current.findPositionByDistance(100)).toEqual([47.377, 8.5418]);

      // Closest to 80m should be 100m point
      expect(result.current.findPositionByDistance(80)).toEqual([47.377, 8.5418]);

      // Closest to 30m should be 0m point
      expect(result.current.findPositionByDistance(30)).toEqual([47.3769, 8.5417]);
    });

    it("returns null when no positions available", () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));
      expect(result.current.findPositionByDistance(0)).toBeNull();
    });
  });

  describe("axis modes", () => {
    it("initializes with time mode for all charts", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      expect(result.current.axisModes.speed).toBe("time");
      expect(result.current.axisModes.hr).toBe("time");
      expect(result.current.axisModes.power).toBe("time");
      expect(result.current.axisModes.elevation).toBe("time");
    });

    it("toggleAxis switches between time and distance", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

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

    it("toggleAxis only affects the specified chart", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      act(() => {
        result.current.toggleAxis("speed");
      });

      expect(result.current.axisModes.speed).toBe("distance");
      expect(result.current.axisModes.hr).toBe("time");
      expect(result.current.axisModes.power).toBe("time");
      expect(result.current.axisModes.elevation).toBe("time");
    });
  });

  describe("hover state", () => {
    it("initializes with null hovered position", () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));
      expect(result.current.hoveredPosition).toBeNull();
    });

    it("setHoveredPosition updates the hovered position", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      act(() => {
        result.current.setHoveredPosition([47.3769, 8.5417]);
      });

      expect(result.current.hoveredPosition).toEqual([47.3769, 8.5417]);
    });

    it("setHoveredPosition can clear the position", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      act(() => {
        result.current.setHoveredPosition([47.3769, 8.5417]);
      });
      expect(result.current.hoveredPosition).not.toBeNull();

      act(() => {
        result.current.setHoveredPosition(null);
      });
      expect(result.current.hoveredPosition).toBeNull();
    });
  });

  describe("expanded chart state", () => {
    it("initializes with null expanded chart", () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));
      expect(result.current.expandedChart).toBeNull();
    });

    it("setExpandedChart updates the expanded chart", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      act(() => {
        result.current.setExpandedChart("power");
      });

      expect(result.current.expandedChart).toBe("power");
    });

    it("setExpandedChart can clear the expansion", async () => {
      const { result } = renderHook(() => useActivityRecords("test-uuid-1"));

      act(() => {
        result.current.setExpandedChart("power");
      });

      act(() => {
        result.current.setExpandedChart(null);
      });

      expect(result.current.expandedChart).toBeNull();
    });
  });
});
