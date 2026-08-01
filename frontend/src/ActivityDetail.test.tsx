import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ActivityDetail } from "./ActivityDetail";

vi.mock("./api", () => ({
  fetchActivity: vi.fn().mockResolvedValue({
    id: 1,
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
  }),
  fetchActivityRecords: vi.fn().mockResolvedValue({
    type: "FeatureCollection",
    activity_id: 1,
    features: [
      {
        type: "Feature",
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
        type: "Feature",
        geometry: { type: "Point", coordinates: [8.5418, 47.377] },
        properties: {
          timestamp: "2024-03-15T10:00:01",
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
        id: 2,
        started_at: "2024-03-10T08:00:00",
        total_distance_m: 38000,
        moving_time_s: 3500,
        elapsed_time_s: 3600,
        elevation_gain_m: 180,
        avg_speed_mps: 7.5,
        avg_hr_bpm: 135,
        avg_power_w: 220,
        max_speed_mps: 10.0,
        max_hr_bpm: 155,
      },
    ],
  }),
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
          properties: { timestamp: "2024-03-10T08:00:00", distance_m: 0, speed_mps: 7.5 },
        },
      ],
    },
  }),
}));

describe("ActivityDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders summary stat tiles from activity data", async () => {
    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("40.0 km")).toBeInTheDocument();
      expect(screen.getByText("1h 0m")).toBeInTheDocument();
      expect(screen.getByText("200 m")).toBeInTheDocument();
    });
  });

  it("renders all chart series headings", async () => {
    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("Speed")).toBeInTheDocument();
      expect(screen.getByText("Heart Rate")).toBeInTheDocument();
      expect(screen.getByText("Power")).toBeInTheDocument();
      expect(screen.getAllByText("Elevation").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("defaults to time axis for all charts", async () => {
    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      const buttons = screen.getAllByText(/Axis: time/);
      expect(buttons).toHaveLength(4);
    });
  });

  it("toggles a chart to distance axis on button click", async () => {
    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("Speed")).toBeInTheDocument();
    });
    const speedButtons = screen.getAllByText(/Axis: time/);
    fireEvent.click(speedButtons[0]);
    await waitFor(() => {
      const distanceButtons = screen.getAllByText(/Axis: distance/);
      expect(distanceButtons).toHaveLength(1);
      // Verify other charts still on time
      const timeButtons = screen.getAllByText(/Axis: time/);
      expect(timeButtons).toHaveLength(3);
    });
  });

  it("renders comparison picker when same-route activities exist", async () => {
    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("Compare with:")).toBeInTheDocument();
    });
  });

  it("renders time gap curve heading when comparison is active", async () => {
    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("Compare with:")).toBeInTheDocument();
    });
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "2" } });
    await waitFor(() => {
      expect(screen.getByText("Time Gap (vs other ride)")).toBeInTheDocument();
    });
  });

  it("renders no-overlap message when routes do not match", async () => {
    const { fetchComparison } = await import("./api");
    (fetchComparison as ReturnType<typeof vi.fn>).mockResolvedValue({
      comparable: false,
      gap_series: [],
      other_geojson: null,
    });

    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("Compare with:")).toBeInTheDocument();
    });
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "2" } });
    await waitFor(() => {
      expect(screen.getByText("These rides are not on the same route and cannot be compared.")).toBeInTheDocument();
    });
  });

  it("renders gap series data in time gap curve when comparison active", async () => {
    const { fetchComparison } = await import("./api");
    (fetchComparison as ReturnType<typeof vi.fn>).mockResolvedValue({
      comparable: true,
      gap_series: [
        { distance_m: 0, gap_s: 0 },
        { distance_m: 50, gap_s: -5 },
        { distance_m: 100, gap_s: 3 },
      ],
      other_geojson: {
        type: "FeatureCollection",
        features: [],
      },
    });

    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("Compare with:")).toBeInTheDocument();
    });
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "2" } });
    await waitFor(() => {
      expect(screen.getByText("Time Gap (vs other ride)")).toBeInTheDocument();
    });
  });
});