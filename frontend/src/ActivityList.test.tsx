import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ActivityList } from "./ActivityList";

vi.mock("./api", () => ({
  fetchActivities: vi.fn(),
  login: vi.fn(),
  uploadFit: vi.fn(),
  register: vi.fn(),
  ACTIVITY_TYPES: ["road", "gravel", "mtb", "virtual", "indoor", "commute", "ebike", "other"],
  ACTIVITY_TYPE_LABELS: {
    road: "Road",
    gravel: "Gravel",
    mtb: "MTB",
    virtual: "Virtual",
    indoor: "Indoor",
    commute: "Commute",
    ebike: "E-bike",
    other: "Other",
  },
}));

import { fetchActivities } from "./api";

const mockFetchActivities = vi.mocked(fetchActivities);

const baseActivity = {
  title: null as string | null,
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
  // Training metrics
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
  // Peaks and breakthrough
  peaks: [],
  is_breakthrough: false,
  // Map
  map_polyline: null as string | null,
  utc_offset_minutes: null as number | null,
  activity_type: null,
  // Bike
  bike_id: null as number | null,
  bike: null,
  // Aero estimation
  estimated_cda: null,
  estimated_crr: null,
  aero_confidence: null,
  weather_status: null,
  effective_ftp: null,
  effective_lthr: null,
};

// Helper to render with router
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};

describe("ActivityList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders rows from mocked API response", async () => {
    mockFetchActivities.mockResolvedValue({
      activities: [
        { id: "uuid-1", ...baseActivity },
        { id: "uuid-2", ...baseActivity, started_at: "2024-03-10T08:00:00", total_distance_m: 25000 },
      ],
      pagination: { page: 1, per_page: 20, total: 2, total_pages: 1 },
    });

    renderWithRouter(<ActivityList onSelect={() => {}} />);

    await waitFor(() => {
      // Distance text appears in both desktop and mobile views
      expect(screen.getAllByText("40.0 km").length).toBeGreaterThan(0);
      expect(screen.getAllByText("25.0 km").length).toBeGreaterThan(0);
    });
  });

  it("renders empty state when no activities", async () => {
    mockFetchActivities.mockResolvedValue({
      activities: [],
      pagination: { page: 1, per_page: 20, total: 0, total_pages: 0 },
    });

    renderWithRouter(<ActivityList onSelect={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("No activities yet")).toBeInTheDocument();
    });
  });

  it("calls onSelect with activity id when row is clicked", async () => {
    mockFetchActivities.mockResolvedValue({
      activities: [{ id: "uuid-42", ...baseActivity }],
      pagination: { page: 1, per_page: 20, total: 1, total_pages: 1 },
    });

    const onSelect = vi.fn();
    renderWithRouter(<ActivityList onSelect={onSelect} />);

    await waitFor(() => {
      // Distance text appears in both desktop and mobile views
      expect(screen.getAllByText("40.0 km").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByText("40.0 km")[0]);
    expect(onSelect).toHaveBeenCalledWith("uuid-42");
  });
});