import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { CalcLabPage } from "./CalcLabPage";

// Mock API
vi.mock("@/api/activities", () => ({
  fetchActivity: vi.fn(),
  fetchWhatIf: vi.fn(),
}));

import { fetchActivity, fetchWhatIf } from "@/api/activities";

const mockFetchActivity = vi.mocked(fetchActivity);
const mockFetchWhatIf = vi.mocked(fetchWhatIf);

function renderCalcLab(activityId: string) {
  return render(
    <MemoryRouter initialEntries={[`/activities/${activityId}/calc-lab`]}>
      <Routes>
        <Route path="/activities/:id/calc-lab" element={<CalcLabPage />} />
        <Route path="/activities/:id" element={<div data-testid="activity-detail">Activity Detail</div>} />
      </Routes>
    </MemoryRouter>
  );
}

const mockActivity = {
  id: "test-activity-1",
  title: "Morning Ride",
  title_source: "auto" as const,
  started_at: "2024-08-15T07:30:00Z",
  total_distance_m: 52000,
  moving_time_s: 5400,
  elapsed_time_s: 5600,
  elevation_gain_m: 620,
  avg_speed_mps: 9.6,
  avg_hr_bpm: 152,
  avg_power_w: 218,
  max_speed_mps: 15.2,
  max_hr_bpm: 178,
  np_power_w: 245,
  intensity_factor: 0.875,
  tss: 87.3,
  training_load: 87,
  power_zone_times: { "1": 180, "2": 1200, "3": 1800, "4": 1500, "5": 600, "6": 120, "7": 0 },
  hr_zone_times: { "1": 300, "2": 1500, "3": 2000, "4": 1200, "5": 400 },
  wbal_min_joules: 4200,
  wbal_min_pct: 19,
  power_source: "measured" as const,
  power_confidence: 1.0,
  peaks: [
    { duration_seconds: 5, watts: 850, all_time_pr: 900, pct_of_pr: 94.4, is_pr: false },
    { duration_seconds: 60, watts: 365, all_time_pr: 380, pct_of_pr: 96.1, is_pr: false },
    { duration_seconds: 300, watts: 320, all_time_pr: 320, pct_of_pr: 100, is_pr: true },
    { duration_seconds: 1200, watts: 275, all_time_pr: 280, pct_of_pr: 98.2, is_pr: false },
  ],
  is_breakthrough: false,
  map_polyline: null,
  utc_offset_minutes: 120,
  activity_type: "road" as const,
  bike_id: null,
  bike: null,
  estimated_cda: null,
  estimated_crr: null,
  aero_confidence: null,
  weather_status: null,
  effective_ftp: 280,
  effective_lthr: 165,
  calc_trace: {
    power_zones: [
      { zone: 1, name: "Active Recovery", min_watts: 0, max_watts: 154 },
      { zone: 2, name: "Endurance", min_watts: 157, max_watts: 210 },
      { zone: 3, name: "Tempo", min_watts: 213, max_watts: 252 },
      { zone: 4, name: "Threshold", min_watts: 255, max_watts: 294 },
      { zone: 5, name: "VO2max", min_watts: 297, max_watts: 336 },
      { zone: 6, name: "Anaerobic", min_watts: 339, max_watts: 420 },
      { zone: 7, name: "Neuromuscular", min_watts: 423, max_watts: null },
    ],
    hr_zones: [
      { zone: 1, name: "Recovery", min_bpm: 0, max_bpm: 133 },
      { zone: 2, name: "Aerobic", min_bpm: 135, max_bpm: 146 },
      { zone: 3, name: "Tempo", min_bpm: 148, max_bpm: 153 },
      { zone: 4, name: "Threshold", min_bpm: 155, max_bpm: 163 },
      { zone: 5, name: "Anaerobic", min_bpm: 165, max_bpm: null },
    ],
    power_zone_times: { 1: 180, 2: 1200, 3: 1800, 4: 1500, 5: 600, 6: 120, 7: 0 },
    hr_zone_times: { 1: 300, 2: 1500, 3: 2000, 4: 1200, 5: 400 },
    wbal_curve: [
      { elapsed_s: 0, wbal_joules: 16800, wbal_pct: 100 },
      { elapsed_s: 30, wbal_joules: 15200, wbal_pct: 90.5 },
      { elapsed_s: 60, wbal_joules: 12000, wbal_pct: 71.4 },
    ],
    w_prime_joules: 16800,
    cp_watts: 280,
    peak_windows: [
      { duration_seconds: 5, watts: 850, start_index: 120, end_index: 124 },
      { duration_seconds: 60, watts: 365, start_index: 300, end_index: 359 },
    ],
  },
};

describe("CalcLabPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Loading and Error States", () => {
    it("shows loading skeleton while fetching", async () => {
      mockFetchActivity.mockImplementation(() => new Promise(() => {})); // Never resolves

      renderCalcLab("test-activity-1");

      expect(screen.getByTestId("loading-skeleton")).toBeInTheDocument();
    });

    it("shows error message when fetch fails", async () => {
      mockFetchActivity.mockRejectedValue(new Error("Network error"));

      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("Network error")).toBeInTheDocument();
      });
      expect(screen.getByRole("button", { name: /go back/i })).toBeInTheDocument();
    });

    it("shows activity not found for missing activity", async () => {
      mockFetchActivity.mockRejectedValue(new Error("Activity not found"));

      renderCalcLab("nonexistent");

      await waitFor(() => {
        expect(screen.getByText("Activity not found")).toBeInTheDocument();
      });
    });
  });

  describe("Content Display", () => {
    beforeEach(() => {
      mockFetchActivity.mockResolvedValue(mockActivity);
    });

    it("shows activity title and date", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText(/Morning Ride/)).toBeInTheDocument();
      });
    });

    it("shows page header with Calc Lab title", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "Calc Lab" })).toBeInTheDocument();
      });
    });

    it("shows back link to activity detail", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText(/back to activity/i)).toBeInTheDocument();
      });
    });

    it("shows effective FTP and LTHR in inputs section", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByLabelText("FTP")).toHaveValue(280);
      });
      expect(screen.getByLabelText("LTHR")).toHaveValue(165);
    });

    it("shows Normalized Power", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("Normalized Power (NP)")).toBeInTheDocument();
      });
      expect(screen.getByText("245.0")).toBeInTheDocument();
    });

    it("shows Intensity Factor", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("Intensity Factor (IF)")).toBeInTheDocument();
      });
    });

    it("shows TSS", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("Training Stress Score (TSS)")).toBeInTheDocument();
      });
    });

    it("shows power zone boundaries", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        // Should have both Power Zones and HR Zones sections
        expect(screen.getByText("Power Zones")).toBeInTheDocument();
      });
      // Check for zone labels
      expect(screen.getAllByText("Z1").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Z7").length).toBeGreaterThanOrEqual(1);
    });

    it("shows HR zone section", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("HR Zones")).toBeInTheDocument();
      });
      // HR zones should show Z1-Z5
      expect(screen.getAllByText("Z5").length).toBeGreaterThanOrEqual(1);
    });

    it("shows peak powers", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("Best Average Power at Duration")).toBeInTheDocument();
      });
      expect(screen.getByText("850W")).toBeInTheDocument();
      expect(screen.getByText("5s")).toBeInTheDocument();
    });

    it("shows W'bal analysis", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("CP")).toBeInTheDocument();
      });
      expect(screen.getByText("280W")).toBeInTheDocument();
      expect(screen.getByText("16.8kJ")).toBeInTheDocument(); // W'
    });

    it("shows W'bal chart", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("W'bal Over Time")).toBeInTheDocument();
      });
    });
  });

  describe("What-If Editing", () => {
    beforeEach(() => {
      mockFetchActivity.mockResolvedValue(mockActivity);
      mockFetchWhatIf.mockResolvedValue({
        activity_id: "test-activity-1",
        what_if_params: { ftp: 300 },
        calc_trace: mockActivity.calc_trace,
      });
    });

    it("shows Reset All button when values are changed", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByLabelText("FTP")).toBeInTheDocument();
      });

      // Initially no reset button
      expect(screen.queryByRole("button", { name: /reset all/i })).not.toBeInTheDocument();

      // Change FTP
      fireEvent.change(screen.getByLabelText("FTP"), { target: { value: "300" } });

      // Reset button should appear
      await waitFor(() => {
        expect(screen.getByRole("button", { name: /reset all/i })).toBeInTheDocument();
      });
    });

    it("shows (was X) indicator when input is changed", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByLabelText("FTP")).toBeInTheDocument();
      });

      // Change FTP
      fireEvent.change(screen.getByLabelText("FTP"), { target: { value: "300" } });

      // Should show original value
      await waitFor(() => {
        expect(screen.getByText("(was 280)")).toBeInTheDocument();
      });
    });
  });

  describe("Expandable Formulas", () => {
    beforeEach(() => {
      mockFetchActivity.mockResolvedValue(mockActivity);
    });

    it("clicking formula expands to show explanation", async () => {
      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText("Normalized Power (NP)")).toBeInTheDocument();
      });

      // Click to expand
      fireEvent.click(screen.getByText("Normalized Power (NP)"));

      // Explanation should now be visible
      await waitFor(() => {
        expect(screen.getByText(/variability of power output/i)).toBeInTheDocument();
      });
    });
  });

  describe("Missing Data Handling", () => {
    it("shows message when no W'bal data", async () => {
      mockFetchActivity.mockResolvedValue({
        ...mockActivity,
        calc_trace: {
          ...mockActivity.calc_trace,
          wbal_curve: null,
          w_prime_joules: null,
          cp_watts: null,
        },
      });

      renderCalcLab("test-activity-1");

      await waitFor(() => {
        expect(screen.getByText(/W'bal data not available/i)).toBeInTheDocument();
      });
    });
  });
});
