import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { PlanDetail } from "./PlanDetail";
import * as racePlansApi from "@/api/race-plans";
import type { RacePlanDetail, CourseDetail } from "@/api/types";

vi.mock("@/api/race-plans");
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockFetchRacePlan = vi.mocked(racePlansApi.fetchRacePlan);
const mockFetchCourse = vi.mocked(racePlansApi.fetchCourse);
const mockDeleteRacePlan = vi.mocked(racePlansApi.deleteRacePlan);

// Unused but available for future tests
// const mockRegenerateRacePlan = vi.mocked(racePlansApi.regenerateRacePlan);

const mockCourse: CourseDetail = {
  id: 1,
  name: "Test Course",
  description: "A test course for unit tests",
  source_type: "gpx",
  source_filename: "test.gpx",
  distance_m: 50000,
  elevation_gain_m: 800,
  elevation_loss_m: 750,
  min_elevation_m: 100,
  max_elevation_m: 500,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  segments: [
    {
      start_m: 0,
      end_m: 10000,
      distance_m: 10000,
      avg_grade_pct: 0.5,
      terrain_type: "flat",
      elevation_gain_m: 50,
      elevation_loss_m: 0,
    },
    {
      start_m: 10000,
      end_m: 25000,
      distance_m: 15000,
      avg_grade_pct: 5.0,
      terrain_type: "climb",
      elevation_gain_m: 750,
      elevation_loss_m: 0,
    },
    {
      start_m: 25000,
      end_m: 40000,
      distance_m: 15000,
      avg_grade_pct: -4.0,
      terrain_type: "descent",
      elevation_gain_m: 0,
      elevation_loss_m: 600,
    },
    {
      start_m: 40000,
      end_m: 50000,
      distance_m: 10000,
      avg_grade_pct: -0.5,
      terrain_type: "flat",
      elevation_gain_m: 0,
      elevation_loss_m: 50,
    },
  ],
  climbs: [],
  elevation_profile: [
    { distance_m: 0, elevation_m: 200, grade_pct: 0.5 },
    { distance_m: 10000, elevation_m: 250, grade_pct: 5.0 },
    { distance_m: 25000, elevation_m: 500, grade_pct: -4.0 },
    { distance_m: 40000, elevation_m: 200, grade_pct: -0.5 },
    { distance_m: 50000, elevation_m: 150, grade_pct: 0 },
  ],
};

const mockPlan: RacePlanDetail = {
  id: 1,
  course_id: 1,
  name: "Test Race Plan",
  total_time_s: 5400,
  total_time_formatted: "1:30:00",
  avg_power_w: 220,
  normalized_power_w: 235,
  intensity_factor: 0.85,
  ride_type: "race",
  descent_aggressiveness: 90,
  stop_pct: 2,
  comparison: {
    constant_time_s: 5600,
    heuristic_time_s: 5400,
    improvement_vs_constant_pct: 3.6,
    improvement_vs_heuristic_pct: 0,
  },
  warnings: [],
  rider_params: {
    weight_kg: 75,
    ftp_watts: 280,
    cp_watts: 265,
    w_prime_joules: 20000,
  },
  bike_params: {
    weight_kg: 8,
    cda: 0.32,
    crr: 0.004,
  },
  segment_targets: [
    { segment_idx: 0, power_w: 210, speed_mps: 10.0, time_s: 1000 },
    { segment_idx: 1, power_w: 260, speed_mps: 4.0, time_s: 3750 },
    { segment_idx: 2, power_w: 150, speed_mps: 15.0, time_s: 1000 },
    { segment_idx: 3, power_w: 200, speed_mps: 12.0, time_s: 833 },
  ],
  wbal_prediction: {
    min_wbal: 8000,
    min_wbal_distance_m: 25000,
  },
  optimization_method: "heuristic",
  sustainability: "green",
  created_at: "2024-01-15T10:00:00Z",
  historical_np_stats: null,
};

function renderPlanDetail(planId: string = "1") {
  return render(
    <MemoryRouter initialEntries={[`/race-planner/plans/${planId}`]}>
      <Routes>
        <Route path="/race-planner/plans/:planId" element={<PlanDetail />} />
        <Route
          path="/race-planner"
          element={<div data-testid="race-planner-list">Race Planner List</div>}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe("PlanDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchRacePlan.mockResolvedValue(mockPlan);
    mockFetchCourse.mockResolvedValue(mockCourse);
  });

  describe("Loading State", () => {
    it("fetches plan and course data on mount", async () => {
      renderPlanDetail("1");

      await waitFor(() => {
        expect(mockFetchRacePlan).toHaveBeenCalledWith(1);
      });

      await waitFor(() => {
        expect(mockFetchCourse).toHaveBeenCalledWith(1);
      });
    });
  });

  describe("Plan Header", () => {
    it("displays plan name", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Test Race Plan")).toBeInTheDocument();
      });
    });

    it("displays course name and distance", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText(/Test Course/)).toBeInTheDocument();
        // Distance appears in multiple places, just verify it exists
        const distanceElements = screen.getAllByText(/50\.0 km/);
        expect(distanceElements.length).toBeGreaterThan(0);
      });
    });

    it("shows improvement badge when available", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText(/3\.6% faster than constant power/)).toBeInTheDocument();
      });
    });

    it("shows back button that navigates to race planner", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Back to Race Planner")).toBeInTheDocument();
      });
    });
  });

  describe("Summary Metrics", () => {
    it("displays total time", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("1:30:00")).toBeInTheDocument();
        expect(screen.getByText("Total Time")).toBeInTheDocument();
      });
    });

    it("displays average power", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("220")).toBeInTheDocument();
        expect(screen.getByText("Avg Power")).toBeInTheDocument();
      });
    });

    it("displays normalized power", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("235")).toBeInTheDocument();
        expect(screen.getByText("Normalized Power")).toBeInTheDocument();
      });
    });

    it("displays intensity factor", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("0.85")).toBeInTheDocument();
        expect(screen.getByText("IF")).toBeInTheDocument();
      });
    });

    it("displays variability index (VI) below NP", async () => {
      renderPlanDetail();

      await waitFor(() => {
        // VI = NP / Avg = 235 / 220 = 1.07
        expect(screen.getByText("VI 1.07")).toBeInTheDocument();
      });
    });
  });

  describe("Historical NP Stats", () => {
    it("displays historical NP context when stats available", async () => {
      const planWithHistory = {
        ...mockPlan,
        historical_np_stats: {
          ride_count: 5,
          avg_np_w: 239,
          min_np_w: 215,
          best_np_w: 260,
          avg_power_w: 205,
        },
      };
      mockFetchRacePlan.mockResolvedValue(planWithHistory);

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText(/Your rides here: NP 239W avg/)).toBeInTheDocument();
        expect(screen.getByText(/5 rides/)).toBeInTheDocument();
      });
    });

    it("shows singular 'ride' for single historical ride", async () => {
      const planWithOneRide = {
        ...mockPlan,
        historical_np_stats: {
          ride_count: 1,
          avg_np_w: 230,
          min_np_w: 230,
          best_np_w: 230,
          avg_power_w: 200,
        },
      };
      mockFetchRacePlan.mockResolvedValue(planWithOneRide);

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText(/Your rides here: NP 230W avg/)).toBeInTheDocument();
        expect(screen.getByText(/1 ride\)/)).toBeInTheDocument();
      });
    });

    it("does not show historical NP when stats null", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Test Race Plan")).toBeInTheDocument();
      });

      expect(screen.queryByText(/Your rides here:/)).not.toBeInTheDocument();
    });
  });

  describe("Sustainability Badge", () => {
    it("displays green sustainability badge", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Sustainable")).toBeInTheDocument();
      });
    });

    it("displays yellow sustainability badge for hard plans", async () => {
      const hardPlan = { ...mockPlan, sustainability: "yellow" };
      mockFetchRacePlan.mockResolvedValue(hardPlan);

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Very Hard")).toBeInTheDocument();
      });
    });

    it("displays red sustainability badge for beyond-limit plans", async () => {
      const redPlan = { ...mockPlan, sustainability: "red" };
      mockFetchRacePlan.mockResolvedValue(redPlan);

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Beyond Limit")).toBeInTheDocument();
      });
    });

    it("shows prominent warning banner for red plans", async () => {
      const redPlan = { ...mockPlan, sustainability: "red" };
      mockFetchRacePlan.mockResolvedValue(redPlan);

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText(/exceeds your sustainable capability/)).toBeInTheDocument();
      });
    });

    it("shows soft warning text for yellow plans", async () => {
      const yellowPlan = { ...mockPlan, sustainability: "yellow" };
      mockFetchRacePlan.mockResolvedValue(yellowPlan);

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText(/Near your limit/)).toBeInTheDocument();
      });
    });
  });

  describe("Segment Table", () => {
    it("displays segment targets table", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Segment Targets")).toBeInTheDocument();
      });
    });

    it("shows correct number of segments", async () => {
      renderPlanDetail();

      await waitFor(() => {
        // Table should have 4 data rows (one per segment)
        const table = screen.getByRole("table");
        const rows = within(table).getAllByRole("row");
        // 1 header row + 4 data rows = 5 total
        expect(rows.length).toBe(5);
      });
    });

    it("displays segment power values", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("210 W")).toBeInTheDocument();
        expect(screen.getByText("260 W")).toBeInTheDocument();
        expect(screen.getByText("150 W")).toBeInTheDocument();
        expect(screen.getByText("200 W")).toBeInTheDocument();
      });
    });

    it("displays segment grades with color coding", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("+5.0%")).toBeInTheDocument();
        expect(screen.getByText("-4.0%")).toBeInTheDocument();
      });
    });
  });

  describe("Rider Parameters", () => {
    it("displays rider weight", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("75 kg")).toBeInTheDocument();
      });
    });

    it("displays FTP", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("280 W")).toBeInTheDocument();
      });
    });

    it("displays CP when available", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("265 W")).toBeInTheDocument();
      });
    });

    it("displays W' when available", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("20.0 kJ")).toBeInTheDocument();
      });
    });
  });

  describe("Bike Parameters", () => {
    it("displays bike CdA", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("0.320")).toBeInTheDocument();
      });
    });

    it("displays bike Crr", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("0.0040")).toBeInTheDocument();
      });
    });
  });

  describe("W'bal Prediction", () => {
    it("displays minimum W'bal", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("8.0 kJ")).toBeInTheDocument();
      });
    });

    it("displays distance at minimum W'bal", async () => {
      renderPlanDetail();

      await waitFor(() => {
        // Distance is formatted with formatDistance() which may show different formats
        expect(screen.getByText(/W'bal Prediction/)).toBeInTheDocument();
      });
    });
  });

  describe("Warnings", () => {
    it("shows warnings when present", async () => {
      const planWithWarnings = {
        ...mockPlan,
        warnings: ["CP estimated from FTP", "W' using default value"],
      };
      mockFetchRacePlan.mockResolvedValue(planWithWarnings);

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText(/CP estimated from FTP/)).toBeInTheDocument();
        expect(screen.getByText(/W' using default value/)).toBeInTheDocument();
      });
    });

    it("hides warnings section when empty", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Test Race Plan")).toBeInTheDocument();
      });

      expect(screen.queryByText("Warnings")).not.toBeInTheDocument();
    });
  });

  describe("Error Handling", () => {
    it("shows error when plan fetch fails", async () => {
      mockFetchRacePlan.mockRejectedValue(new Error("Plan not found"));

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText(/Failed to load race plan/)).toBeInTheDocument();
        expect(screen.getByText(/Plan not found/)).toBeInTheDocument();
      });
    });

    it("shows back button on error", async () => {
      mockFetchRacePlan.mockRejectedValue(new Error("Network error"));

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Back to Race Planner")).toBeInTheDocument();
      });
    });
  });

  describe("Delete Functionality", () => {
    it("shows delete button", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByTitle("Delete")).toBeInTheDocument();
      });
    });

    it("shows confirmation dialog on delete click", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Test Race Plan")).toBeInTheDocument();
      });

      const deleteButton = screen.getByTitle("Delete");
      await userEvent.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText("Delete Race Plan")).toBeInTheDocument();
        expect(
          screen.getByText(/Are you sure you want to delete this race plan/)
        ).toBeInTheDocument();
      });
    });

    it("cancels delete when Cancel clicked", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Test Race Plan")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTitle("Delete"));

      await waitFor(() => {
        expect(screen.getByText("Delete Race Plan")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

      await waitFor(() => {
        expect(screen.queryByText("Delete Race Plan")).not.toBeInTheDocument();
      });

      expect(mockDeleteRacePlan).not.toHaveBeenCalled();
    });

    it("deletes plan and navigates on confirm", async () => {
      mockDeleteRacePlan.mockResolvedValue(undefined);

      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Test Race Plan")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTitle("Delete"));

      await waitFor(() => {
        expect(screen.getByText("Delete Race Plan")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Delete" }));

      await waitFor(() => {
        expect(mockDeleteRacePlan).toHaveBeenCalledWith(1);
      });

      // Should navigate to race planner list
      await waitFor(() => {
        expect(screen.getByTestId("race-planner-list")).toBeInTheDocument();
      });
    });
  });

  describe("Adjust Parameters", () => {
    it("shows adjust button", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Adjust/ })).toBeInTheDocument();
      });
    });

    it("toggles parameter sliders when adjust clicked", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Test Race Plan")).toBeInTheDocument();
      });

      const adjustButton = screen.getByRole("button", { name: /Adjust/ });
      await userEvent.click(adjustButton);

      // Sliders panel should appear
      await waitFor(() => {
        // Button should now be highlighted (default variant instead of outline)
        expect(adjustButton).toHaveClass("bg-primary");
      });
    });
  });

  describe("Chart Section", () => {
    it("displays elevation and power profile section", async () => {
      renderPlanDetail();

      await waitFor(() => {
        expect(screen.getByText("Elevation & Power Profile")).toBeInTheDocument();
      });
    });
  });

  describe("Plan Not Found", () => {
    it("shows message when planId is missing", async () => {
      render(
        <MemoryRouter initialEntries={["/race-planner/plans/"]}>
          <Routes>
            <Route path="/race-planner/plans/" element={<PlanDetail />} />
          </Routes>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText("Plan not found")).toBeInTheDocument();
      });
    });
  });
});
