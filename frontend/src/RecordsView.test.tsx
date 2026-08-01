import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { RecordsView } from "./RecordsView";

vi.mock("./api", () => ({
  fetchRecords: vi.fn(),
}));

import { fetchRecords } from "./api";

const mockFetchRecords = vi.mocked(fetchRecords);

const fullResponse = {
  lifetime_prs: {
    longest_distance_m: { value: 50000, activity_id: 1 },
    longest_moving_time_s: { value: 5400, activity_id: 1 },
    fastest_5000_m: { value: 600, activity_id: 1 },
    fastest_10000_m: { value: 1200, activity_id: 2 },
    fastest_40000_m: { value: 5400, activity_id: 3 },
    max_speed_mps: { value: 15.0, activity_id: 1 },
    max_hr_bpm: { value: 185, activity_id: 2 },
    biggest_elevation_gain_m: { value: 1200, activity_id: 3 },
    highest_sustained_power_w: null,
  },
  route_prs: [
    { route_id: 1, route_label: "2024-03-15", fastest_time_s: 3600, activity_id: 1 },
    { route_id: 2, route_label: "2024-03-10", fastest_time_s: 5400, activity_id: 3 },
  ],
};

describe("RecordsView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders lifetime PR tiles from mocked API response", async () => {
    mockFetchRecords.mockResolvedValue(fullResponse);

    render(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("Lifetime PRs")).toBeInTheDocument();
      expect(screen.getByText("50.0 km")).toBeInTheDocument();
      expect(screen.getByText("54.0 km/h")).toBeInTheDocument();
      expect(screen.getByText("185 bpm")).toBeInTheDocument();
    });
  });

  it("renders per-route PR tiles when route data is present", async () => {
    mockFetchRecords.mockResolvedValue(fullResponse);

    render(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("Route PRs")).toBeInTheDocument();
      expect(screen.getByText("Route 2024-03-15")).toBeInTheDocument();
      expect(screen.getByText("1h 0m")).toBeInTheDocument();
      expect(screen.getByText("Route 2024-03-10")).toBeInTheDocument();
    });
  });

  it("omits route PRs section when no routes matched", async () => {
    mockFetchRecords.mockResolvedValue({
      lifetime_prs: {
        longest_distance_m: { value: 50000, activity_id: 1 },
        longest_moving_time_s: null,
        fastest_5000_m: null,
        fastest_10000_m: null,
        fastest_40000_m: null,
        max_speed_mps: null,
        max_hr_bpm: null,
        biggest_elevation_gain_m: null,
        highest_sustained_power_w: null,
      },
      route_prs: [],
    });

    render(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("Lifetime PRs")).toBeInTheDocument();
      expect(screen.queryByText("Route PRs")).not.toBeInTheDocument();
    });
  });

  it("renders empty state when no records", async () => {
    mockFetchRecords.mockResolvedValue({
      lifetime_prs: {
        longest_distance_m: null,
        longest_moving_time_s: null,
        fastest_5000_m: null,
        fastest_10000_m: null,
        fastest_40000_m: null,
        max_speed_mps: null,
        max_hr_bpm: null,
        biggest_elevation_gain_m: null,
        highest_sustained_power_w: null,
      },
      route_prs: [],
    });

    render(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("No activities yet. Upload a FIT file to see your PRs.")).toBeInTheDocument();
    });
  });
});