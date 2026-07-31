import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

  it("renders the speed chart heading", async () => {
    render(<ActivityDetail activityId={1} onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("Speed")).toBeInTheDocument();
    });
  });
});