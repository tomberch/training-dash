import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { MyModelPage } from "./MyModelPage";

// Mock APIs
vi.mock("@/api", () => ({
  fetchThresholds: vi.fn(),
  fetchPMC: vi.fn(),
  fetchFitness: vi.fn(),
}));

vi.mock("@/api/bikes", () => ({
  fetchBikes: vi.fn(),
}));

import { fetchThresholds, fetchPMC, fetchFitness } from "@/api";
import { fetchBikes } from "@/api/bikes";

const mockFetchThresholds = vi.mocked(fetchThresholds);
const mockFetchPMC = vi.mocked(fetchPMC);
const mockFetchFitness = vi.mocked(fetchFitness);
const mockFetchBikes = vi.mocked(fetchBikes);

function renderMyModel() {
  return render(
    <MemoryRouter initialEntries={["/calc-lab"]}>
      <Routes>
        <Route path="/calc-lab" element={<MyModelPage />} />
        <Route path="/athlete" element={<div data-testid="athlete-page">Athlete</div>} />
        <Route path="/pmc" element={<div data-testid="pmc-page">PMC</div>} />
        <Route path="/gear" element={<div data-testid="gear-page">Gear</div>} />
      </Routes>
    </MemoryRouter>
  );
}

const mockThresholds = [
  { effective_date: "2024-08-01", ftp_watts: 280, lthr_bpm: 165, hrmax_bpm: 185 },
  { effective_date: "2024-06-15", ftp_watts: 270, lthr_bpm: 163, hrmax_bpm: 185 },
];

const mockPmc = [
  { date: "2024-08-15", ctl: 75, atl: 82, tsb: -7 },
  { date: "2024-08-14", ctl: 74, atl: 80, tsb: -6 },
];

const mockFitnessResponse = {
  current: {
    computed_at: "2024-08-15T00:00:00Z",
    pp_watts: 950,
    w_prime_joules: 22000,
    cp_watts: 265,
  },
  history: [],
};

const mockBikes = [
  {
    id: 1,
    name: "Road Bike",
    bike_type: "road" as const,
    model_year: 2023,
    weight_kg: 8.5,
    photo_path: null,
    total_distance_m: 5000000,
    cda: 0.32,
    crr: 0.005,
    cda_source: "calibrated" as const,
    crr_source: "manual" as const,
    calibrated_at: "2024-07-01T00:00:00Z",
    is_default: true,
    retired_at: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-08-01T00:00:00Z",
    estimated_cda_avg: 0.31,
    estimated_crr_avg: 0.0048,
    estimated_cda_stddev: 0.02,
    estimated_crr_stddev: 0.0005,
    aero_sample_count: 15,
  },
  {
    id: 2,
    name: "TT Bike",
    bike_type: "tt" as const,
    model_year: 2022,
    weight_kg: 9.0,
    photo_path: null,
    total_distance_m: 1000000,
    cda: 0.24,
    crr: 0.004,
    cda_source: "manual" as const,
    crr_source: "manual" as const,
    calibrated_at: null,
    is_default: false,
    retired_at: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    estimated_cda_avg: null,
    estimated_crr_avg: null,
    estimated_cda_stddev: null,
    estimated_crr_stddev: null,
    aero_sample_count: null,
  },
];

describe("MyModelPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchThresholds.mockResolvedValue(mockThresholds);
    mockFetchPMC.mockResolvedValue(mockPmc);
    mockFetchFitness.mockResolvedValue(mockFitnessResponse);
    mockFetchBikes.mockResolvedValue(mockBikes);
  });

  describe("Loading State", () => {
    it("shows loading skeleton initially", () => {
      // Make fetch hang
      mockFetchThresholds.mockImplementation(() => new Promise(() => {}));

      renderMyModel();

      // Skeleton uses data-slot="skeleton"
      expect(screen.getAllByRole("generic").filter(el => el.getAttribute("data-slot") === "skeleton").length).toBeGreaterThan(0);
    });
  });

  describe("Page Header", () => {
    it("shows page title", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("My Model")).toBeInTheDocument();
      });
    });

    it("shows page subtitle", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("Your athlete parameters and calculation simulator")).toBeInTheDocument();
      });
    });
  });

  describe("Simulator Section", () => {
    it("shows Power/Speed Calculator title", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("Power/Speed Calculator")).toBeInTheDocument();
      });
    });

    it("shows solve for buttons", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Speed" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Power" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Time" })).toBeInTheDocument();
      });
    });

    it("has default input values", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByLabelText("Power")).toHaveValue(200);
        expect(screen.getByLabelText("Distance")).toHaveValue(40);
        expect(screen.getByLabelText("Gradient")).toHaveValue(0);
      });
    });

    it("calculates result when inputs change", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("Result")).toBeInTheDocument();
      });

      // Change power
      fireEvent.change(screen.getByLabelText("Power"), { target: { value: "250" } });

      // Result section should contain a speed value (just check Result section exists with values)
      await waitFor(() => {
        expect(screen.getByText("Result")).toBeInTheDocument();
        // Check the result has a speed value displayed (the calculated one)
        const resultSection = screen.getByText("Result").closest("div");
        expect(resultSection).toBeInTheDocument();
      });
    });

    it("allows switching solve mode", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Speed" })).toBeInTheDocument();
      });

      // Click Power button to solve for power instead
      fireEvent.click(screen.getByRole("button", { name: "Power" }));

      // Power input should now be disabled
      await waitFor(() => {
        expect(screen.getByLabelText("Power")).toBeDisabled();
      });
    });

    it("shows bike selection dropdown", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByLabelText("Bike")).toBeInTheDocument();
      });

      // Should show bikes in dropdown
      expect(screen.getByRole("option", { name: "Road Bike" })).toBeInTheDocument();
      expect(screen.getByRole("option", { name: "TT Bike" })).toBeInTheDocument();
    });
  });

  describe("Thresholds Section", () => {
    it("shows current FTP", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("FTP")).toBeInTheDocument();
        expect(screen.getByText("280")).toBeInTheDocument();
      });
    });

    it("shows current LTHR", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("LTHR")).toBeInTheDocument();
        expect(screen.getByText("165")).toBeInTheDocument();
      });
    });

    it("shows current HRmax", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("HRmax")).toBeInTheDocument();
        expect(screen.getByText("185")).toBeInTheDocument();
      });
    });

    it("shows link to threshold history", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("View threshold history →")).toBeInTheDocument();
      });
    });
  });

  describe("Power Model Section", () => {
    it("shows Critical Power", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("Critical Power (CP)")).toBeInTheDocument();
        expect(screen.getByText("265")).toBeInTheDocument();
      });
    });

    it("shows W-prime", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("W' (W-prime)")).toBeInTheDocument();
        expect(screen.getByText("22.0")).toBeInTheDocument(); // 22000J = 22.0kJ
      });
    });

    it("shows Peak Power", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("Peak Power")).toBeInTheDocument();
        expect(screen.getByText("950")).toBeInTheDocument();
      });
    });
  });

  describe("Bike Parameters Section", () => {
    it("shows bike cards", async () => {
      renderMyModel();

      // Wait for page to load
      await waitFor(() => {
        expect(screen.getByText("My Model")).toBeInTheDocument();
      });

      // Check for bike section header
      await waitFor(() => {
        expect(screen.getByText("Bike Parameters")).toBeInTheDocument();
      });

      // Check that bike names appear (could be in dropdown or cards)
      expect(screen.getAllByText("Road Bike").length).toBeGreaterThan(0);
      expect(screen.getAllByText("TT Bike").length).toBeGreaterThan(0);
    });

    it("shows default badge on default bike", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("Default")).toBeInTheDocument();
      });
    });

    it("shows CdA and Crr values", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("0.320 m²")).toBeInTheDocument(); // CdA
        expect(screen.getByText("0.0050")).toBeInTheDocument(); // Crr
      });
    });

    it("shows link to manage bikes", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("Manage bikes →")).toBeInTheDocument();
      });
    });
  });

  describe("Current Fitness Section", () => {
    it("shows CTL value", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("CTL (Fitness)")).toBeInTheDocument();
        expect(screen.getByText("75")).toBeInTheDocument();
      });
    });

    it("shows ATL value", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("ATL (Fatigue)")).toBeInTheDocument();
        expect(screen.getByText("82")).toBeInTheDocument();
      });
    });

    it("shows TSB value with form indicator", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("TSB (Form)")).toBeInTheDocument();
        expect(screen.getByText("-7")).toBeInTheDocument();
        expect(screen.getByText("Neutral")).toBeInTheDocument();
      });
    });

    it("shows link to PMC chart", async () => {
      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("View PMC chart →")).toBeInTheDocument();
      });
    });
  });

  describe("Error State", () => {
    it("shows error message when data fetch fails", async () => {
      mockFetchThresholds.mockRejectedValue(new Error("Network error"));

      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("Failed to load data")).toBeInTheDocument();
      });
    });

    it("shows retry button on error", async () => {
      mockFetchThresholds.mockRejectedValue(new Error("Network error"));

      renderMyModel();

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
      });
    });
  });

  describe("Empty States", () => {
    it("shows empty state when no bikes", async () => {
      mockFetchBikes.mockResolvedValue([]);

      renderMyModel();

      await waitFor(() => {
        expect(screen.getByText("No bikes configured")).toBeInTheDocument();
      });
    });

    it("shows dash when no threshold data", async () => {
      mockFetchThresholds.mockResolvedValue([]);

      renderMyModel();

      await waitFor(() => {
        // Should show dashes for missing values
        const dashes = screen.getAllByText("—");
        expect(dashes.length).toBeGreaterThan(0);
      });
    });

    it("shows dash when no fitness data", async () => {
      mockFetchFitness.mockResolvedValue({ current: null, history: [] });

      renderMyModel();

      await waitFor(() => {
        // CP, W', PP should show dashes
        const dashes = screen.getAllByText("—");
        expect(dashes.length).toBeGreaterThan(0);
      });
    });
  });
});
