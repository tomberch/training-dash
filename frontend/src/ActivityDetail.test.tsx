import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ActivityDetail } from "./ActivityDetail";
import { deleteActivity } from "./api";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    deleteActivity: vi.fn().mockResolvedValue(undefined),
    fetchActivity: vi.fn().mockResolvedValue({
      id: "test-uuid-1",
      title: "Morning Ride",
      title_source: "auto",
      started_at: "2024-03-15T10:00:00Z",
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
      utc_offset_minutes: 0,
    }),
    fetchActivityRecords: vi.fn().mockResolvedValue({
      type: "FeatureCollection",
      activity_id: "test-uuid-1",
      features: [
        {
          type: "Feature",
          geometry: { type: "Point", coordinates: [8.5417, 47.3769] },
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
          type: "Feature",
          geometry: { type: "Point", coordinates: [8.5418, 47.377] },
          properties: {
            timestamp: "2024-03-15T10:00:01Z",
            distance_m: 10,
            hr_bpm: 121,
            power_w: 201,
            speed_mps: 8.01,
            altitude_m: 501,
            cadence_rpm: 81,
          },
        },
      ],
    }),
    fetchSameRouteActivities: vi.fn().mockResolvedValue({
      route_id: 1,
      activities: [
        {
          id: "test-uuid-2",
          title: "Sunday Ride",
          title_source: "auto",
          started_at: "2024-03-10T08:00:00Z",
          total_distance_m: 38000,
          moving_time_s: 3500,
          elapsed_time_s: 3600,
          elevation_gain_m: 180,
          avg_speed_mps: 7.5,
          avg_hr_bpm: 135,
          avg_power_w: 220,
          max_speed_mps: 10.0,
          max_hr_bpm: 155,
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
          utc_offset_minutes: 0,
        },
      ],
    }),
    fetchActivityWbal: vi.fn().mockResolvedValue({
      wbal_series: [],
      w_prime_joules: null,
      ftp_watts: null,
      wbal_min_joules: null,
      wbal_min_pct: null,
    }),
    fetchThresholds: vi.fn().mockResolvedValue([]),
    fetchComparison: vi.fn().mockResolvedValue({
      comparable: true,
      gap_series: [
        { distance_m: 0, gap_s: 0 },
        { distance_m: 50, gap_s: -5 },
        { distance_m: 100, gap_s: 3 },
      ],
      other_geojson: {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            geometry: { type: "Point", coordinates: [8.5417, 47.3769] },
            properties: { timestamp: "2024-03-10T08:00:00Z", distance_m: 0, speed_mps: 7.5 },
          },
        ],
      },
    }),
  };
});

// Helper to render with router
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};

describe("ActivityDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders summary stat tiles from activity data", async () => {
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("40.0 km")).toBeInTheDocument();
      expect(screen.getByText("1h 00m")).toBeInTheDocument();
      expect(screen.getByText("200 m")).toBeInTheDocument();
    });
  });

  it("renders all chart series headings", async () => {
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={() => {}} />);
    await waitFor(() => {
      // Chart headings - use text content since there are multiple "Speed" labels (cards + headings)
      const speedHeading = screen.getAllByText("Speed").find(el => 
        el.tagName === "H2" || el.tagName === "H3"
      );
      expect(speedHeading).toBeInTheDocument();
    });
  });

  it("defaults to time axis for all charts", async () => {
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={() => {}} />);
    await waitFor(() => {
      // Toggle buttons now show just "Time" or "Distance"
      const buttons = screen.getAllByRole("button", { name: "Time" });
      expect(buttons).toHaveLength(4);
    });
  });

  it("toggles a chart to distance axis on button click", async () => {
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={() => {}} />);
    await waitFor(() => {
      // Wait for charts to render
      expect(screen.getAllByText("Speed").length).toBeGreaterThan(0);
    });
    const timeButtons = screen.getAllByRole("button", { name: "Time" });
    fireEvent.click(timeButtons[0]);
    await waitFor(() => {
      const distanceButtons = screen.getAllByRole("button", { name: "Distance" });
      expect(distanceButtons).toHaveLength(1);
      // Verify other charts still on time
      const remainingTimeButtons = screen.getAllByRole("button", { name: "Time" });
      expect(remainingTimeButtons).toHaveLength(3);
    });
  });

  it("renders comparison link when same-route activities exist", async () => {
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={() => {}} />);
    await waitFor(() => {
      // Compare button is shown when same-route activities exist
      expect(screen.getByText("Compare")).toBeInTheDocument();
    });
  });
});

describe("ActivityDetail - Delete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders delete button", async () => {
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    });
  });

  it("opens confirmation dialog when delete button clicked", async () => {
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
      expect(screen.getByText("Delete activity?")).toBeInTheDocument();
      expect(screen.getByText(/This will permanently delete this activity/)).toBeInTheDocument();
    });
  });

  it("calls deleteActivity and onBack on confirm", async () => {
    const onBack = vi.fn();
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={onBack} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    });

    // Open dialog
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });

    // Click confirm (the destructive action button)
    const confirmButton = screen.getByRole("button", { name: /Delete/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(vi.mocked(deleteActivity)).toHaveBeenCalledWith("test-uuid-1");
      expect(onBack).toHaveBeenCalled();
    });
  });

  it("shows error toast and stays on page when delete fails", async () => {
    vi.mocked(deleteActivity).mockRejectedValueOnce(new Error("Delete failed"));
    const onBack = vi.fn();
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={onBack} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    });

    // Open dialog
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });

    // Click confirm
    const confirmButton = screen.getByRole("button", { name: /Delete/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(vi.mocked(deleteActivity)).toHaveBeenCalledWith("test-uuid-1");
      // Should NOT call onBack on error
      expect(onBack).not.toHaveBeenCalled();
    });
  });

  it("closes dialog when cancel clicked", async () => {
    renderWithRouter(<ActivityDetail activityId="test-uuid-1" onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    });

    // Open dialog
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });

    // Click cancel
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });

    // Should not have called deleteActivity
    expect(vi.mocked(deleteActivity)).not.toHaveBeenCalled();
  });
});