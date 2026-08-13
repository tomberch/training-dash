import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RecordsView } from "./RecordsView";

vi.mock("./api", () => ({
  fetchRecords: vi.fn(),
}));

import { fetchRecords } from "./api";

const mockFetchRecords = vi.mocked(fetchRecords);

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const fullResponse = {
  lifetime_prs: {
    longest_distance_m: { value: 50000, activity_id: "uuid-1" },
    longest_moving_time_s: { value: 5400, activity_id: "uuid-1" },
    fastest_5000_m: { value: 600, activity_id: "uuid-1" },
    fastest_10000_m: { value: 1200, activity_id: "uuid-2" },
    fastest_40000_m: { value: 5400, activity_id: "uuid-3" },
    max_speed_mps: { value: 15.0, activity_id: "uuid-1" },
    max_hr_bpm: { value: 185, activity_id: "uuid-2" },
    biggest_elevation_gain_m: { value: 1200, activity_id: "uuid-3" },
    highest_sustained_power_w: null,
  },
  route_prs: [
    { route_id: 1, route_label: "Morning Ride", fastest_time_s: 3600, activity_id: "uuid-1", activity_title: "Morning Ride", polyline: "abc123" },
    { route_id: 2, route_label: "Afternoon Ride", fastest_time_s: 5400, activity_id: "uuid-3", activity_title: "Afternoon Ride", polyline: "def456" },
  ],
};

describe("RecordsView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders lifetime PR tiles from mocked API response", async () => {
    mockFetchRecords.mockResolvedValue(fullResponse);

    renderWithRouter(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("Lifetime PRs")).toBeInTheDocument();
      expect(screen.getByText("50.0 km")).toBeInTheDocument();
      expect(screen.getByText("54.0 km/h")).toBeInTheDocument();
      expect(screen.getByText("185 bpm")).toBeInTheDocument();
    });
  });

  it("renders per-route PR tiles when route data is present", async () => {
    mockFetchRecords.mockResolvedValue(fullResponse);

    renderWithRouter(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("Route PRs")).toBeInTheDocument();
      expect(screen.getByText("Morning Ride")).toBeInTheDocument();
      expect(screen.getByText("1h 0m 0s")).toBeInTheDocument();
      expect(screen.getByText("Afternoon Ride")).toBeInTheDocument();
    });
  });

  it("omits route PRs section when no routes matched", async () => {
    mockFetchRecords.mockResolvedValue({
      lifetime_prs: {
        longest_distance_m: { value: 50000, activity_id: "uuid-1" },
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

    renderWithRouter(<RecordsView />);

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

    renderWithRouter(<RecordsView />);

    await waitFor(() => {
      expect(screen.getByText("No personal records yet")).toBeInTheDocument();
    });
  });
});