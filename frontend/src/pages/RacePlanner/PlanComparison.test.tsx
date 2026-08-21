import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { PlanComparison } from "./PlanComparison";
import * as racePlansApi from "@/api/race-plans";
import type {
  RacePlanDetail,
  CourseDetail,
  ExecutionComparison,
  MatchingActivity,
} from "@/api/types";

vi.mock("@/api/race-plans");

const mockFetchRacePlan = vi.mocked(racePlansApi.fetchRacePlan);
const mockFetchCourse = vi.mocked(racePlansApi.fetchCourse);
const mockCompareExecution = vi.mocked(racePlansApi.compareExecution);
const mockFetchMatchingActivities = vi.mocked(racePlansApi.fetchMatchingActivities);

// =============================================================================
// Test Data
// =============================================================================

const mockPlan: RacePlanDetail = {
  id: 1,
  course_id: 10,
  name: "Test Race Plan",
  avg_power_w: 250,
  normalized_power_w: 255,
  intensity_factor: 0.85,
  total_time_s: 7200,
  total_time_formatted: "2:00:00",
  optimization_method: "weighted_time_in_zones",
  created_at: "2025-01-01T10:00:00Z",
  comparison: {
    heuristic_time_s: 7300,
    optimized_time_s: 7200,
    improvement_vs_heuristic_pct: 1.4,
  },
  warnings: [],
  segment_targets: [
    {
      segment_idx: 0,
      power_w: 240,
      time_s: 3600,
      speed_mps: 6.94,
    },
    {
      segment_idx: 1,
      power_w: 260,
      time_s: 3600,
      speed_mps: 6.94,
    },
  ],
  wbal_prediction: null,
  rider_params: {
    weight_kg: 75,
    ftp_watts: 280,
    cp_watts: 290,
    w_prime_joules: 20000,
  },
  bike_params: {
    weight_kg: 8,
    cda: 0.32,
    crr: 0.004,
  },
};

const mockCourse: CourseDetail = {
  id: 10,
  name: "Test Course",
  description: null,
  source_type: "gpx",
  source_filename: "test.gpx",
  distance_m: 50000,
  elevation_gain_m: 500,
  elevation_loss_m: 500,
  min_elevation_m: 100,
  max_elevation_m: 350,
  created_at: "2025-01-01T09:00:00Z",
  updated_at: "2025-01-01T09:00:00Z",
  segments: [
    {
      start_m: 0,
      end_m: 25000,
      distance_m: 25000,
      avg_grade_pct: 1.0,
      elevation_gain_m: 250,
      elevation_loss_m: 0,
      terrain_type: "climb",
    },
    {
      start_m: 25000,
      end_m: 50000,
      distance_m: 25000,
      avg_grade_pct: -1.0,
      elevation_gain_m: 0,
      elevation_loss_m: 250,
      terrain_type: "descent",
    },
  ],
  climbs: [],
  elevation_profile: [],
};

const mockComparison: ExecutionComparison = {
  plan_id: 1,
  activity_id: "abc-123",
  total_planned_time_s: 7200,
  total_planned_time_formatted: "2:00:00",
  total_actual_time_s: 7140,
  total_actual_time_formatted: "1:59:00",
  time_delta_s: -60,
  time_delta_formatted: "-1:00",
  time_delta_pct: -0.83,
  pacing_consistency: 85,
  segments_over_target: 1,
  segments_under_target: 0,
  segment_comparisons: [
    {
      segment_idx: 0,
      distance_m: 25000,
      grade_pct: 1.0,
      planned_power_w: 240,
      actual_power_w: 250,
      power_delta_pct: 4.2,
      planned_time_s: 3600,
      actual_time_s: 3540,
      time_delta_s: -60,
    },
    {
      segment_idx: 1,
      distance_m: 25000,
      grade_pct: -1.0,
      planned_power_w: 260,
      actual_power_w: 255,
      power_delta_pct: -1.9,
      planned_time_s: 3600,
      actual_time_s: 3600,
      time_delta_s: 0,
    },
  ],
  insights: ["Good pacing on climbs", "Power within target range"],
};

const mockMatchingActivities: MatchingActivity[] = [
  {
    id: "activity-1",
    name: "Morning Ride",
    started_at: "2025-01-10T08:00:00Z",
    total_distance_m: 49500,
    moving_time_s: 7000,
    avg_power_w: 245,
  },
  {
    id: "activity-2",
    name: "Evening Spin",
    started_at: "2025-01-08T17:30:00Z",
    total_distance_m: 50200,
    moving_time_s: 7300,
    avg_power_w: 238,
  },
];

// =============================================================================
// Test Helpers
// =============================================================================

function renderWithPlanAndActivity(planId: string, activityId?: string) {
  const path = activityId
    ? `/race-planner/plans/${planId}/compare/${activityId}`
    : `/race-planner/plans/${planId}/compare`;

  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/race-planner/plans/:planId/compare/:activityId?"
          element={<PlanComparison />}
        />
        <Route
          path="/race-planner/plans/:planId"
          element={<div data-testid="plan-detail">Plan Detail</div>}
        />
        <Route
          path="/race-planner"
          element={<div data-testid="race-planner">Race Planner</div>}
        />
      </Routes>
    </MemoryRouter>
  );
}

// =============================================================================
// Tests
// =============================================================================

describe("PlanComparison", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchRacePlan.mockResolvedValue(mockPlan);
    mockFetchCourse.mockResolvedValue(mockCourse);
    mockCompareExecution.mockResolvedValue(mockComparison);
    mockFetchMatchingActivities.mockResolvedValue(mockMatchingActivities);
  });

  // ===========================================================================
  // Activity Selection Mode (no activityId)
  // ===========================================================================

  describe("Activity Selection Mode", () => {
    it("shows activity selector when no activityId provided", async () => {
      renderWithPlanAndActivity("1");

      await waitFor(() => {
        expect(screen.getByText("Compare Execution")).toBeInTheDocument();
      });
      expect(screen.getByText(/Select an activity/)).toBeInTheDocument();
    });

    it("displays matching activities", async () => {
      renderWithPlanAndActivity("1");

      await waitFor(() => {
        expect(screen.getByText("Morning Ride")).toBeInTheDocument();
      });
      expect(screen.getByText("Evening Spin")).toBeInTheDocument();
    });

    it("shows activity power and duration", async () => {
      renderWithPlanAndActivity("1");

      await waitFor(() => {
        expect(screen.getByText("245 W")).toBeInTheDocument();
      });
      expect(screen.getByText("238 W")).toBeInTheDocument();
    });

    it("shows empty state when no matching activities", async () => {
      mockFetchMatchingActivities.mockResolvedValue([]);

      renderWithPlanAndActivity("1");

      await waitFor(() => {
        expect(screen.getByText("No matching activities found")).toBeInTheDocument();
      });
    });

    it("navigates to comparison on activity selection", async () => {
      renderWithPlanAndActivity("1");

      await waitFor(() => {
        expect(screen.getByText("Morning Ride")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Morning Ride"));

      // Should navigate - we verify by seeing comparison view load
      await waitFor(() => {
        expect(mockCompareExecution).toHaveBeenCalledWith(1, "activity-1");
      });
    });

    it("has back link to plan detail", async () => {
      renderWithPlanAndActivity("1");

      await waitFor(() => {
        expect(screen.getByText("Back to Plan")).toBeInTheDocument();
      });
    });
  });

  // ===========================================================================
  // Comparison View (with activityId)
  // ===========================================================================

  describe("Comparison View", () => {
    it("displays comparison header", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Execution Comparison")).toBeInTheDocument();
      });
    });

    it("shows plan name and distance", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText(/Test Race Plan/)).toBeInTheDocument();
      });
      expect(screen.getByText(/50\.0 km/)).toBeInTheDocument();
    });

    it("displays time delta prominently", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("-1:00")).toBeInTheDocument();
      });
      expect(screen.getByText(/Faster/)).toBeInTheDocument();
    });

    it("shows planned and actual times", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("2:00:00")).toBeInTheDocument();
      });
      expect(screen.getByText("1:59:00")).toBeInTheDocument();
    });

    it("displays pacing consistency score", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("85")).toBeInTheDocument();
      });
      expect(screen.getByText("out of 100")).toBeInTheDocument();
    });

    it("shows segments over/under target", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Over Target")).toBeInTheDocument();
      });
      expect(screen.getByText("Under Target")).toBeInTheDocument();
    });
  });

  // ===========================================================================
  // Segment Comparison Table
  // ===========================================================================

  describe("Segment Comparison Table", () => {
    it("displays segment table", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Segment Comparison")).toBeInTheDocument();
      });
    });

    it("shows segment grades", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("+1.0%")).toBeInTheDocument();
      });
      expect(screen.getByText("-1.0%")).toBeInTheDocument();
    });

    it("shows planned and actual power", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("240 W")).toBeInTheDocument();
      });
      expect(screen.getByText("250 W")).toBeInTheDocument();
      expect(screen.getByText("260 W")).toBeInTheDocument();
      expect(screen.getByText("255 W")).toBeInTheDocument();
    });

    it("shows power delta percentages", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("+4.2%")).toBeInTheDocument();
      });
      expect(screen.getByText("-1.9%")).toBeInTheDocument();
    });

    it("shows time delta in seconds", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("-60s")).toBeInTheDocument();
      });
    });

    it("allows sorting by power delta", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Power Δ")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Power Δ"));
      // Verify table is still visible (sort applied)
      expect(screen.getByText("Segment Comparison")).toBeInTheDocument();
    });

    it("allows sorting by time delta", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Time Δ")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Time Δ"));
      expect(screen.getByText("Segment Comparison")).toBeInTheDocument();
    });
  });

  // ===========================================================================
  // Power Comparison Chart
  // ===========================================================================

  describe("Power Comparison Chart", () => {
    it("displays chart section", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Power: Planned vs Actual")).toBeInTheDocument();
      });
    });

    it("shows chart legend", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        // "Planned" and "Actual" appear in both chart legend and table header
        expect(screen.getAllByText("Planned").length).toBeGreaterThan(0);
      });
      expect(screen.getAllByText("Actual").length).toBeGreaterThan(0);
    });
  });

  // ===========================================================================
  // Insights Section
  // ===========================================================================

  describe("Insights Section", () => {
    it("displays pacing insights", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Pacing Insights")).toBeInTheDocument();
      });
    });

    it("shows individual insights", async () => {
      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Good pacing on climbs")).toBeInTheDocument();
      });
      expect(screen.getByText("Power within target range")).toBeInTheDocument();
    });

    it("hides insights section when no insights", async () => {
      mockCompareExecution.mockResolvedValue({
        ...mockComparison,
        insights: [],
      });

      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Execution Comparison")).toBeInTheDocument();
      });
      expect(screen.queryByText("Pacing Insights")).not.toBeInTheDocument();
    });
  });

  // ===========================================================================
  // Slower Execution Display
  // ===========================================================================

  describe("Slower Execution Display", () => {
    it("shows Slower label when actual time exceeds plan", async () => {
      mockCompareExecution.mockResolvedValue({
        ...mockComparison,
        time_delta_s: 120,
        time_delta_formatted: "+2:00",
      });

      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("+2:00")).toBeInTheDocument();
      });
      expect(screen.getByText(/Slower/)).toBeInTheDocument();
    });
  });

  // ===========================================================================
  // Error Handling
  // ===========================================================================

  describe("Error Handling", () => {
    it("displays error when plan fetch fails", async () => {
      mockFetchRacePlan.mockRejectedValue(new Error("Failed to load plan"));

      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText(/Failed to load comparison/)).toBeInTheDocument();
      });
    });

    it("displays error when comparison fetch fails", async () => {
      mockCompareExecution.mockRejectedValue(new Error("Comparison failed"));

      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText(/Failed to load comparison/)).toBeInTheDocument();
      });
    });

    it("shows back button on error", async () => {
      mockFetchRacePlan.mockRejectedValue(new Error("Error"));

      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Back to Race Planner")).toBeInTheDocument();
      });
    });
  });

  // ===========================================================================
  // Null/Missing Data Handling
  // ===========================================================================

  describe("Null Data Handling", () => {
    it("handles null actual power in segments", async () => {
      mockCompareExecution.mockResolvedValue({
        ...mockComparison,
        segment_comparisons: [
          {
            segment_idx: 0,
            distance_m: 25000,
            grade_pct: 1.0,
            planned_power_w: 240,
            actual_power_w: null,
            power_delta_pct: null,
            planned_time_s: 3600,
            actual_time_s: null,
            time_delta_s: null,
          },
        ],
      });

      renderWithPlanAndActivity("1", "abc-123");

      await waitFor(() => {
        expect(screen.getByText("Segment Comparison")).toBeInTheDocument();
      });
      // Should show dash for null values
      expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    });

    it("handles untitled activity in selector", async () => {
      mockFetchMatchingActivities.mockResolvedValue([
        {
          id: "activity-1",
          name: null,
          started_at: "2025-01-10T08:00:00Z",
          total_distance_m: 49500,
          moving_time_s: 7000,
          avg_power_w: null,
        },
      ]);

      renderWithPlanAndActivity("1");

      await waitFor(() => {
        expect(screen.getByText("Untitled Ride")).toBeInTheDocument();
      });
    });
  });
});
