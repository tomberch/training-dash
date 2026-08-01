import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { RecordsView } from "./RecordsView";

vi.mock("./api", () => ({
  fetchRecords: vi.fn(),
}));

import { fetchRecords } from "./api";

const mockFetchRecords = vi.mocked(fetchRecords);

const fullRecords = {
  longest_distance_m: { value: 50000, activity_id: 1 },
  longest_moving_time_s: { value: 5400, activity_id: 1 },
  fastest_5000_m: { value: 600, activity_id: 1 },
  fastest_10000_m: { value: 1200, activity_id: 2 },
  fastest_40000_m: { value: 5400, activity_id: 3 },
  max_speed_mps: { value: 15.0, activity_id: 1 },
  max_hr_bpm: { value: 185, activity_id: 2 },
  biggest_elevation_gain_m: { value: 1200, activity_id: 3 },
  highest_sustained_power_w: null,
};

describe("RecordsView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders PR tiles from mocked API response", async () => {
    mockFetchRecords.mockResolvedValue(fullRecords);

    render(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("Longest Ride")).toBeInTheDocument();
      expect(screen.getByText("50.0 km")).toBeInTheDocument();
      expect(screen.getByText("Fastest 5km")).toBeInTheDocument();
      expect(screen.getByText("10m 0s")).toBeInTheDocument();
      expect(screen.getByText("Max Speed")).toBeInTheDocument();
      expect(screen.getByText("54.0 km/h")).toBeInTheDocument();
      expect(screen.getByText("Max HR")).toBeInTheDocument();
      expect(screen.getByText("185 bpm")).toBeInTheDocument();
      expect(screen.getByText("Biggest Climb")).toBeInTheDocument();
      expect(screen.getByText("1200 m")).toBeInTheDocument();
    });
  });

  it("renders empty state when no records", async () => {
    mockFetchRecords.mockResolvedValue({
      longest_distance_m: null,
      longest_moving_time_s: null,
      fastest_5000_m: null,
      fastest_10000_m: null,
      fastest_40000_m: null,
      max_speed_mps: null,
      max_hr_bpm: null,
      biggest_elevation_gain_m: null,
      highest_sustained_power_w: null,
    });

    render(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("No activities yet. Upload a FIT file to see your PRs.")).toBeInTheDocument();
    });
  });
});