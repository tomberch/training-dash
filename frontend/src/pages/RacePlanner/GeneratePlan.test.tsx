import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { GeneratePlan } from "./GeneratePlan";
import * as racePlansApi from "@/api/race-plans";
import * as bikesApi from "@/api/bikes";
import * as athleteApi from "@/api/athlete";
import { UserContext } from "@/contexts/UserContext";
import type { CourseListItem, CourseDetail, Bike, RacePlanResponse } from "@/api/types";
import type { User } from "@/api/user";

vi.mock("@/api/race-plans");
vi.mock("@/api/bikes");
vi.mock("@/api/athlete");

const mockFetchCourses = vi.mocked(racePlansApi.fetchCourses);
const mockFetchCourse = vi.mocked(racePlansApi.fetchCourse);
const mockGenerateRacePlan = vi.mocked(racePlansApi.generateRacePlan);
const mockFetchBikes = vi.mocked(bikesApi.fetchBikes);
const mockFetchThresholds = vi.mocked(athleteApi.fetchThresholds);

const mockCourse: CourseListItem = {
  id: 1,
  name: "Test Course",
  source_type: "gpx",
  distance_m: 50000,
  elevation_gain_m: 1000,
  created_at: "2024-01-01T00:00:00Z",
};

const mockCourseDetail: CourseDetail = {
  id: 1,
  name: "Test Course",
  description: null,
  source_type: "gpx",
  source_filename: "test.gpx",
  distance_m: 50000,
  elevation_gain_m: 1000,
  elevation_loss_m: 900,
  min_elevation_m: 100,
  max_elevation_m: 500,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  segments: [],
  climbs: [],
  elevation_profile: [],
};

const mockBike: Bike = {
  id: 1,
  name: "Canyon Aeroad",
  bike_type: "road",
  model_year: 2023,
  weight_kg: 7.5,
  photo_path: null,
  total_distance_m: 5000000,
  cda: 0.25,
  crr: 0.004,
  cda_source: "manual",
  crr_source: null,
  calibrated_at: null,
  is_default: true,
  retired_at: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  estimated_cda_avg: null,
  estimated_crr_avg: null,
  estimated_cda_stddev: null,
  estimated_crr_stddev: null,
  aero_sample_count: null,
};

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

const mockPlanResponse: RacePlanResponse = {
  id: 1,
  course_id: 1,
  name: "Test Plan",
  total_time_s: 5400,
  total_time_formatted: "1:30:00",
  avg_power_w: 220,
  normalized_power_w: 230,
  intensity_factor: 0.85,
  comparison: {
    constant_time_s: 5600,
    heuristic_time_s: 5400,
    improvement_vs_constant_pct: 3.5,
  },
  warnings: [],
  optimization_method: "heuristic",
  sustainability: "green",
};

function renderGeneratePlan(initialRoute = "/race-planner/generate") {
  return render(
    <UserContext.Provider value={{ user: mockUser, updateUser: vi.fn() }}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/race-planner/generate" element={<GeneratePlan />} />
          <Route path="/race-planner/courses/:courseId/generate" element={<GeneratePlan />} />
          <Route path="/race-planner/plans/:planId" element={<div data-testid="plan-detail">Plan Detail</div>} />
          <Route path="/race-planner" element={<div data-testid="race-planner">Race Planner</div>} />
        </Routes>
      </MemoryRouter>
    </UserContext.Provider>
  );
}

// Helper to get select elements by their section heading
function getCourseSelect() {
  const section = screen.getByText("Course").closest("section")!;
  return within(section).getByRole("combobox");
}

function getBikeSelect() {
  const section = screen.getByText("Bike").closest("section")!;
  return within(section).getByRole("combobox");
}

describe("GeneratePlan", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchCourses.mockResolvedValue([mockCourse]);
    mockFetchCourse.mockResolvedValue(mockCourseDetail);
    mockFetchBikes.mockResolvedValue([mockBike]);
    mockFetchThresholds.mockResolvedValue([{ effective_date: "2024-01-01", ftp_watts: 280, lthr_bpm: 165, hrmax_bpm: 185 }]);
  });

  describe("Initial Rendering", () => {
    it("renders page title and form sections", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByText("Generate Race Plan")).toBeInTheDocument();
      });

      expect(screen.getByText("Course")).toBeInTheDocument();
      expect(screen.getByText("Bike")).toBeInTheDocument();
      expect(screen.getByText("Rider Parameters")).toBeInTheDocument();
      expect(screen.getByText("Plan Settings")).toBeInTheDocument();
    });

    it("loads courses, bikes, and thresholds on mount", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(mockFetchCourses).toHaveBeenCalled();
        expect(mockFetchBikes).toHaveBeenCalled();
        expect(mockFetchThresholds).toHaveBeenCalled();
      });
    });

    it("pre-fills FTP from thresholds", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });
    });

    it("pre-fills weight from user profile", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("75")).toBeInTheDocument();
      });
    });

    it("selects default bike automatically", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        const bikeSelect = getBikeSelect() as HTMLSelectElement;
        expect(bikeSelect.value).toBe("1");
      });
    });
  });

  describe("Course Selection", () => {
    it("renders course dropdown with options", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByText(/Test Course.*50\.0 km.*1000 m/)).toBeInTheDocument();
      });
    });

    it("shows empty state when no courses", async () => {
      mockFetchCourses.mockResolvedValue([]);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByText("No courses yet")).toBeInTheDocument();
        expect(screen.getByText("Upload a course")).toBeInTheDocument();
      });
    });

    it("loads course details when course is selected", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByText(/Test Course/)).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await waitFor(() => {
        expect(mockFetchCourse).toHaveBeenCalledWith(1);
      });
    });

    it("pre-selects course from URL param", async () => {
      renderGeneratePlan("/race-planner/courses/1/generate");

      await waitFor(() => {
        expect(mockFetchCourse).toHaveBeenCalledWith(1);
      });
    });
  });

  describe("Bike Selection", () => {
    it("shows 'Use defaults' option", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByText("Use defaults (road bike)")).toBeInTheDocument();
      });
    });

    it("shows bike CdA/Crr when bike is selected", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        // Default bike is pre-selected, so details should show
        expect(screen.getByText("CdA: 0.250")).toBeInTheDocument();
        expect(screen.getByText("Crr: 0.0040")).toBeInTheDocument();
      });
    });

    it("shows link to add bike when no bikes exist", async () => {
      mockFetchBikes.mockResolvedValue([]);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByText("Add a bike")).toBeInTheDocument();
      });
    });
  });

  describe("Intensity Slider", () => {
    it("shows intensity percentage and power estimate", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByText("85% of FTP")).toBeInTheDocument();
        expect(screen.getByText(/238 W avg/)).toBeInTheDocument(); // 280 * 0.85
      });
    });
  });

  describe("Optimizer Toggle", () => {
    it("shows optimizer toggle with explicit opt-in labeling", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByText("Optimal Pacing (experimental)")).toBeInTheDocument();
        expect(screen.getByText("Takes 10-30 seconds")).toBeInTheDocument();
      });
    });

    it("shows explanatory copy when optimizer is enabled", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      // Enable optimizer using Testing Library query
      const optimizerSwitch = screen.getByRole("switch", { name: /Optimal Pacing/i });
      await userEvent.click(optimizerSwitch);

      // Should show explanatory copy about W'bal energy budget
      await waitFor(() => {
        expect(screen.getByText(/W′bal energy budget/)).toBeInTheDocument();
        expect(screen.getByText(/strategy view/)).toBeInTheDocument();
      });
    });
  });

  describe("Form Validation", () => {
    it("does not call generate when no course selected", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      // Generate should not have been called
      expect(mockGenerateRacePlan).not.toHaveBeenCalled();
    });

    it("does not call generate when FTP is invalid", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      // Select a course first
      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      // Set invalid FTP
      const ftpInput = screen.getByLabelText(/FTP/);
      await userEvent.clear(ftpInput);
      await userEvent.type(ftpInput, "50");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      // Generate should not have been called
      expect(mockGenerateRacePlan).not.toHaveBeenCalled();
    });
  });

  describe("Plan Generation", () => {
    it("generates plan when form is valid", async () => {
      mockGenerateRacePlan.mockResolvedValue(mockPlanResponse);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      // Select course
      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      // Click generate
      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(mockGenerateRacePlan).toHaveBeenCalledWith(
          expect.objectContaining({
            course_id: 1,
            ftp_watts: 280,
            target_intensity: 0.85,
            use_optimizer: false,
          })
        );
      });
    });

    it("shows loading state during generation", async () => {
      mockGenerateRacePlan.mockImplementation(() => new Promise(() => {})); // Never resolves
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText("Generating...")).toBeInTheDocument();
      });
    });

    it("shows 'Optimizing...' when optimizer is enabled", async () => {
      mockGenerateRacePlan.mockImplementation(() => new Promise(() => {}));
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      // Enable optimizer
      const optimizerSwitch = screen.getByRole("switch", { name: /Optimal Pacing/i });
      await userEvent.click(optimizerSwitch);

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText("Optimizing...")).toBeInTheDocument();
      });
    });

    it("returns to submittable state after generation fails", async () => {
      mockGenerateRacePlan.mockRejectedValue(new Error("Generation failed"));
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      // After failure, button should be back to "Generate Plan" (not "Generating...")
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Generate Plan" })).not.toBeDisabled();
      });
      
      expect(mockGenerateRacePlan).toHaveBeenCalled();
    });
  });

  describe("Quick Preview", () => {
    it("shows quick preview after successful generation", async () => {
      mockGenerateRacePlan.mockResolvedValue(mockPlanResponse);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText("Plan Generated!")).toBeInTheDocument();
        expect(screen.getByText("1:30:00")).toBeInTheDocument();
        expect(screen.getByText("220 W")).toBeInTheDocument();
        expect(screen.getByText("0.85")).toBeInTheDocument();
      });
    });

    it("shows improvement percentage in preview", async () => {
      mockGenerateRacePlan.mockResolvedValue(mockPlanResponse);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText("3.5% faster than constant power")).toBeInTheDocument();
      });
    });

    it("shows warnings in preview if present", async () => {
      const responseWithWarnings = {
        ...mockPlanResponse,
        warnings: ["CP estimated from FTP", "W' using default"],
      };
      mockGenerateRacePlan.mockResolvedValue(responseWithWarnings);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText(/CP estimated from FTP/)).toBeInTheDocument();
      });
    });

    it("navigates to plan detail when clicking View Full Plan", async () => {
      mockGenerateRacePlan.mockResolvedValue(mockPlanResponse);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText("Plan Generated!")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "View Full Plan" }));

      await waitFor(() => {
        expect(screen.getByTestId("plan-detail")).toBeInTheDocument();
      });
    });

    it("resets to form when clicking Generate Another", async () => {
      mockGenerateRacePlan.mockResolvedValue(mockPlanResponse);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText("Plan Generated!")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Generate Another" }));

      await waitFor(() => {
        expect(screen.getByText("Generate Race Plan")).toBeInTheDocument();
        expect(screen.queryByText("Plan Generated!")).not.toBeInTheDocument();
      });
    });

    it("shows 'Optimal Strategy' badge for optimized plans", async () => {
      const optimizedResponse = {
        ...mockPlanResponse,
        optimization_method: "optimized",
      };
      mockGenerateRacePlan.mockResolvedValue(optimizedResponse);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      // Enable optimizer
      const optimizerSwitch = screen.getByRole("switch", { name: /Optimal Pacing/i });
      await userEvent.click(optimizerSwitch);

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText("Plan Generated!")).toBeInTheDocument();
        expect(screen.getByText("Optimal Strategy")).toBeInTheDocument();
      });
    });

    it("does not show 'Optimal Strategy' badge for heuristic plans", async () => {
      mockGenerateRacePlan.mockResolvedValue(mockPlanResponse); // has optimization_method: "heuristic"
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Generate Plan" }));

      await waitFor(() => {
        expect(screen.getByText("Plan Generated!")).toBeInTheDocument();
        expect(screen.queryByText("Optimal Strategy")).not.toBeInTheDocument();
      });
    });
  });

  describe("Target Time Mode", () => {
    it("switches to time mode when toggle clicked", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      // Click on "Target Time" toggle
      await userEvent.click(screen.getByRole("button", { name: "Target Time" }));

      // Should show time input
      await waitFor(() => {
        expect(screen.getByLabelText(/Target Finish Time/)).toBeInTheDocument();
      });
    });

    it("shows terrain-shaped copy in time mode", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Target Time" }));

      // Wait for time input to appear first (confirms mode switch)
      await waitFor(() => {
        expect(screen.getByLabelText(/Target Finish Time/)).toBeInTheDocument();
      });

      // Now check for the terrain-shaped info text
      expect(screen.getByText(/scales your riding profile/i)).toBeInTheDocument();
    });

    it("shows warning that optimizer is not used in time mode", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Target Time" }));

      await waitFor(() => {
        expect(screen.getByText(/energy-budget optimizer is not used/i)).toBeInTheDocument();
      });
    });

    it("submits with target_time_s when in time mode", async () => {
      mockGenerateRacePlan.mockResolvedValue(mockPlanResponse);
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      // Select course
      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      // Switch to time mode
      await userEvent.click(screen.getByRole("button", { name: "Target Time" }));

      // Enter target time (1:30:00 = 5400 seconds)
      const timeInput = screen.getByLabelText(/Target Finish Time/);
      await userEvent.type(timeInput, "1:30:00");

      // Click generate (button text changes in time mode)
      await userEvent.click(screen.getByRole("button", { name: "Scale to Target Time" }));

      await waitFor(() => {
        expect(mockGenerateRacePlan).toHaveBeenCalledWith(
          expect.objectContaining({
            course_id: 1,
            ftp_watts: 280,
            target_time_s: 5400,
          })
        );
      });
    });

    it("shows 'Scaling to target time...' during generation", async () => {
      mockGenerateRacePlan.mockImplementation(() => new Promise(() => {}));
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Target Time" }));

      const timeInput = screen.getByLabelText(/Target Finish Time/);
      await userEvent.type(timeInput, "1:30:00");

      await userEvent.click(screen.getByRole("button", { name: "Scale to Target Time" }));

      await waitFor(() => {
        expect(screen.getByText("Scaling to target time...")).toBeInTheDocument();
      });
    });

    it("disables submit button when time is invalid", async () => {
      renderGeneratePlan();

      await waitFor(() => {
        expect(screen.getByDisplayValue("280")).toBeInTheDocument();
      });

      const courseSelect = getCourseSelect();
      await userEvent.selectOptions(courseSelect, "1");

      await userEvent.click(screen.getByRole("button", { name: "Target Time" }));

      // Enter invalid time
      const timeInput = screen.getByLabelText(/Target Finish Time/);
      await userEvent.type(timeInput, "invalid");

      // Button should be disabled
      expect(screen.getByRole("button", { name: "Scale to Target Time" })).toBeDisabled();
    });
  });
});
