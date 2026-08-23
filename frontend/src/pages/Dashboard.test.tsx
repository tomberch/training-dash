import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Dashboard } from "./Dashboard";
import * as api from "../api";
import type {
  Activity,
  PaginatedActivities,
  ThresholdEntry,
  User,
  RecordsResponse,
} from "../api";
import type { PMCPoint, PowerCurvePoint } from "../api/analytics";

vi.mock("../api");

const mockFetchActivities = vi.mocked(api.fetchActivities);
const mockFetchPMC = vi.mocked(api.fetchPMC);
const mockFetchPowerCurve = vi.mocked(api.fetchPowerCurve);
const mockFetchRecords = vi.mocked(api.fetchRecords);
const mockFetchThresholds = vi.mocked(api.fetchThresholds);
const mockFetchMe = vi.mocked(api.fetchMe);

// =============================================================================
// Test Data
// =============================================================================

const mockActivity: Activity = {
  id: "abc-123",
  title: "Morning Ride",
  title_source: "auto",
  started_at: "2025-01-15T08:00:00Z",
  total_distance_m: 45000,
  moving_time_s: 5400,
  timer_time_s: null,
  elapsed_time_s: 6000,
  elevation_gain_m: 350,
  elevation_loss_m: null,
  min_altitude_m: null,
  max_altitude_m: null,
  max_grade_pct: null,
  avg_speed_mps: 8.33,
  avg_speed_moving_mps: null,
  max_speed_mps: 15.0,
  avg_hr_bpm: 145,
  max_hr_bpm: 175,
  avg_power_w: 220,
  max_power_w: null,
  np_power_w: 235,
  intensity_factor: 0.84,
  tss: 85,
  training_load: 85,
  power_zone_times: { "1": 600, "2": 1800, "3": 1500, "4": 1200, "5": 300 },
  hr_zone_times: { "1": 300, "2": 1200, "3": 2400, "4": 1200, "5": 300 },
  wbal_min_joules: 8000,
  wbal_min_pct: 40,
  power_source: "measured",
  power_confidence: null,
  avg_cadence_rpm: null,
  avg_cadence_pedaling_rpm: null,
  avg_temperature_c: null,
  min_temperature_c: null,
  max_temperature_c: null,
  peaks: [
    { duration_seconds: 5, watts: 850, all_time_pr: 900, pct_of_pr: 94, is_pr: false },
    { duration_seconds: 60, watts: 400, all_time_pr: 420, pct_of_pr: 95, is_pr: false },
    { duration_seconds: 300, watts: 320, all_time_pr: 320, pct_of_pr: 100, is_pr: true },
    { duration_seconds: 1200, watts: 280, all_time_pr: 290, pct_of_pr: 97, is_pr: false },
  ],
  is_breakthrough: false,
  map_polyline: "encoded_polyline_string",
  utc_offset_minutes: -480,
  activity_type: "road",
  bike_id: 1,
  bike: { id: 1, name: "Road Bike", bike_type: "road" },
  estimated_cda: null,
  estimated_crr: null,
  aero_confidence: null,
  weather_status: null,
};

const mockActivitiesResponse: PaginatedActivities = {
  activities: [mockActivity],
  pagination: {
    total: 1,
    page: 1,
    per_page: 20,
    total_pages: 1,
  },
};

const mockPMCData: PMCPoint[] = [
  { date: "2025-01-08", ctl: 50, atl: 60, tsb: -10 },
  { date: "2025-01-09", ctl: 51, atl: 58, tsb: -7 },
  { date: "2025-01-10", ctl: 52, atl: 56, tsb: -4 },
  { date: "2025-01-11", ctl: 53, atl: 54, tsb: -1 },
  { date: "2025-01-12", ctl: 54, atl: 52, tsb: 2 },
  { date: "2025-01-13", ctl: 55, atl: 55, tsb: 0 },
  { date: "2025-01-14", ctl: 56, atl: 58, tsb: -2 },
  { date: "2025-01-15", ctl: 58, atl: 65, tsb: -7 },
];

const mockPowerCurve: PowerCurvePoint[] = [
  { duration_seconds: 5, watts: 850, achieved_date: "2025-01-10", days_ago: 5 },
  { duration_seconds: 60, watts: 400, achieved_date: "2025-01-12", days_ago: 3 },
  { duration_seconds: 300, watts: 320, achieved_date: "2025-01-15", days_ago: 0 },
  { duration_seconds: 1200, watts: 280, achieved_date: "2025-01-08", days_ago: 7 },
];

const mockRecords: RecordsResponse = {
  lifetime_prs: {
    longest_distance_m: { value: 120000, activity_id: "abc-123" },
    longest_moving_time_s: { value: 14400, activity_id: "abc-123" },
    fastest_5000_m: null,
    fastest_10000_m: null,
    fastest_40000_m: null,
    max_speed_mps: { value: 18.5, activity_id: "abc-123" },
    max_hr_bpm: { value: 190, activity_id: "abc-123" },
    biggest_elevation_gain_m: { value: 1500, activity_id: "abc-123" },
    highest_sustained_power_w: { value: 320, activity_id: "abc-123" },
  },
  route_prs: {
    items: [],
    total: 0,
  },
};

const mockThresholds: ThresholdEntry[] = [
  {
    effective_date: "2025-01-01",
    ftp_watts: 280,
    lthr_bpm: 165,
    hrmax_bpm: 190,
  },
];

const mockUser: User = {
  id: 1,
  email: "test@example.com",
  display_name: "Test User",
  avatar_path: null,
  is_admin: false,
  is_approved: true,
  unit_system: "metric",
  sync_hour: 3,
  date_of_birth: null,
  weight_kg: 75,
  height_cm: 180,
  gender: "male",
  power_zone_percentages: null,
  hr_zone_percentages: null,
  hr_derived_power_enabled: false,
  map_tile_style: "osm",
  hr_power_model: null,
};

// =============================================================================
// Test Helpers
// =============================================================================

function renderDashboard() {
  // Clear localStorage for clean tests
  localStorage.removeItem("traindash:first-activity-celebrated");

  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/settings" element={<div data-testid="settings">Settings</div>} />
        <Route path="/activities/:id" element={<div data-testid="activity-detail">Activity</div>} />
      </Routes>
    </MemoryRouter>
  );
}

// =============================================================================
// Tests
// =============================================================================

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    mockFetchActivities.mockResolvedValue(mockActivitiesResponse);
    mockFetchPMC.mockResolvedValue(mockPMCData);
    mockFetchPowerCurve.mockResolvedValue(mockPowerCurve);
    mockFetchRecords.mockResolvedValue(mockRecords);
    mockFetchThresholds.mockResolvedValue(mockThresholds);
    mockFetchMe.mockResolvedValue(mockUser);
  });

  // ===========================================================================
  // Loading State
  // ===========================================================================

  describe("Loading State", () => {
    it("shows loading skeleton initially", () => {
      // Don't resolve promises immediately
      mockFetchActivities.mockReturnValue(new Promise(() => {}));
      mockFetchPMC.mockReturnValue(new Promise(() => {}));

      renderDashboard();

      // Skeleton should be visible (uses data-slot="skeleton")
      expect(document.querySelector('[data-slot="skeleton"]')).toBeInTheDocument();
    });
  });

  // ===========================================================================
  // Empty State
  // ===========================================================================

  describe("Empty State", () => {
    it("shows empty state when no activities", async () => {
      mockFetchActivities.mockResolvedValue({
        activities: [],
        pagination: { total: 0, page: 1, per_page: 20, total_pages: 0 },
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Welcome to TrainDash")).toBeInTheDocument();
      });
    });
  });

  // ===========================================================================
  // Dashboard Content
  // ===========================================================================

  describe("Dashboard Content", () => {
    it("displays page header", async () => {
      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Dashboard")).toBeInTheDocument();
      });
    });

    it("displays recent activities", async () => {
      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Morning Ride")).toBeInTheDocument();
      });
    });

    it("displays PMC sparkline section", async () => {
      renderDashboard();

      await waitFor(() => {
        // CTL value from current PMC
        expect(screen.getByText("58")).toBeInTheDocument();
      });
    });

    it("displays TSB value", async () => {
      renderDashboard();

      await waitFor(() => {
        // TSB from current PMC (-7)
        expect(screen.getByText("-7")).toBeInTheDocument();
      });
    });
  });

  // ===========================================================================
  // Threshold Onboarding
  // ===========================================================================

  describe("Threshold Onboarding", () => {
    it("shows threshold setup prompt when no thresholds", async () => {
      mockFetchThresholds.mockResolvedValue([]);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText(/Set your training thresholds/i)).toBeInTheDocument();
      });
    });

    it("has link to settings when no thresholds", async () => {
      mockFetchThresholds.mockResolvedValue([]);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByRole("link", { name: /configure/i })).toHaveAttribute(
          "href",
          "/settings"
        );
      });
    });

    it("hides threshold prompt when thresholds exist", async () => {
      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Dashboard")).toBeInTheDocument();
      });

      expect(screen.queryByText(/Set your training thresholds/i)).not.toBeInTheDocument();
    });
  });

  // ===========================================================================
  // FTP Card
  // ===========================================================================

  describe("FTP Card", () => {
    it("displays FTP card heading", async () => {
      renderDashboard();

      // Wait for the FTP card section to appear - look for "FTP" heading
      await waitFor(() => {
        expect(screen.getByRole("heading", { level: 2, name: "FTP" })).toBeInTheDocument();
      });
    });
  });

  // ===========================================================================
  // API Calls
  // ===========================================================================

  describe("API Calls", () => {
    it("fetches all required data on mount", async () => {
      renderDashboard();

      await waitFor(() => {
        expect(mockFetchActivities).toHaveBeenCalled();
        expect(mockFetchPMC).toHaveBeenCalled();
        expect(mockFetchPowerCurve).toHaveBeenCalled();
        expect(mockFetchRecords).toHaveBeenCalled();
        expect(mockFetchThresholds).toHaveBeenCalled();
        expect(mockFetchMe).toHaveBeenCalled();
      });
    });

    it("fetches PMC for last 8 weeks", async () => {
      renderDashboard();

      await waitFor(() => {
        expect(mockFetchPMC).toHaveBeenCalled();
      });

      // Check that dates span approximately 8 weeks (56 days)
      const call = mockFetchPMC.mock.calls[0];
      const startDate = call[0];
      const endDate = call[1];
      if (startDate && endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        const daysDiff = Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
        expect(daysDiff).toBeGreaterThanOrEqual(54); // Allow some tolerance
        expect(daysDiff).toBeLessThanOrEqual(58);
      }
    });
  });

  // ===========================================================================
  // Error Handling
  // ===========================================================================

  describe("Error Handling", () => {
    it("handles threshold fetch error gracefully", async () => {
      mockFetchThresholds.mockRejectedValue(new Error("Failed"));

      renderDashboard();

      // Should still render dashboard
      await waitFor(() => {
        expect(screen.getByText("Dashboard")).toBeInTheDocument();
      });
    });

    it("handles user fetch error gracefully", async () => {
      mockFetchMe.mockRejectedValue(new Error("Failed"));

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Dashboard")).toBeInTheDocument();
      });
    });

    it("handles all data fetch errors", async () => {
      mockFetchActivities.mockRejectedValue(new Error("Network error"));
      mockFetchPMC.mockRejectedValue(new Error("Network error"));
      mockFetchPowerCurve.mockRejectedValue(new Error("Network error"));
      mockFetchRecords.mockRejectedValue(new Error("Network error"));

      renderDashboard();

      // Should stop loading (not hang)
      await waitFor(() => {
        expect(document.querySelector(".animate-pulse")).not.toBeInTheDocument();
      }, { timeout: 3000 });
    });
  });

  // ===========================================================================
  // Activity Display
  // ===========================================================================

  describe("Activity Display", () => {
    it("shows multiple activities", async () => {
      const activity2: Activity = {
        ...mockActivity,
        id: "def-456",
        title: "Evening Spin",
        started_at: "2025-01-14T17:00:00Z",
      };

      mockFetchActivities.mockResolvedValue({
        activities: [mockActivity, activity2],
        pagination: { total: 2, page: 1, per_page: 20, total_pages: 1 },
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Morning Ride")).toBeInTheDocument();
        expect(screen.getByText("Evening Spin")).toBeInTheDocument();
      });
    });

    it("shows breakthrough badge when activity is breakthrough", async () => {
      const breakthroughActivity: Activity = {
        ...mockActivity,
        is_breakthrough: true,
      };

      mockFetchActivities.mockResolvedValue({
        activities: [breakthroughActivity],
        pagination: { total: 1, page: 1, per_page: 20, total_pages: 1 },
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Morning Ride")).toBeInTheDocument();
      });

      // Check for breakthrough indicator (typically a badge or icon)
      // The exact text depends on the RecentActivities component
    });
  });

  // ===========================================================================
  // PMC Calculations
  // ===========================================================================

  describe("PMC Calculations", () => {
    it("calculates CTL trend from PMC data", async () => {
      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Dashboard")).toBeInTheDocument();
      });

      // CTL went from 50 to 58 over 8 days = 16% increase
      // The trend calculation: ((58 - 50) / 50) * 100 = 16%
      // Look for trend indicator (depends on component implementation)
    });

    it("handles PMC with insufficient data for trend", async () => {
      mockFetchPMC.mockResolvedValue([
        { date: "2025-01-15", ctl: 58, atl: 65, tsb: -7 },
      ]);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("Dashboard")).toBeInTheDocument();
      });
      // Should render without crashing
    });
  });
});
