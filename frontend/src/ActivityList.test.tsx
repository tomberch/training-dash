import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ActivityList } from "./ActivityList";

vi.mock("./api", () => ({
  fetchActivities: vi.fn(),
  login: vi.fn(),
  uploadFit: vi.fn(),
}));

import { fetchActivities } from "./api";

const mockFetchActivities = vi.mocked(fetchActivities);

const baseActivity = {
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
};

describe("ActivityList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders rows from mocked API response", async () => {
    mockFetchActivities.mockResolvedValue([
      { id: 1, ...baseActivity },
      { id: 2, ...baseActivity, started_at: "2024-03-10T08:00:00", total_distance_m: 25000 },
    ]);

    render(<ActivityList onSelect={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("40.0 km")).toBeInTheDocument();
      expect(screen.getByText("25.0 km")).toBeInTheDocument();
    });
  });

  it("renders empty state when no activities", async () => {
    mockFetchActivities.mockResolvedValue([]);

    render(<ActivityList onSelect={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("No activities yet. Upload a FIT file to get started.")).toBeInTheDocument();
    });
  });

  it("calls onSelect with activity id when row is clicked", async () => {
    mockFetchActivities.mockResolvedValue([{ id: 42, ...baseActivity }]);

    const onSelect = vi.fn();
    render(<ActivityList onSelect={onSelect} />);

    await waitFor(() => {
      expect(screen.getByText("40.0 km")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("40.0 km"));
    expect(onSelect).toHaveBeenCalledWith(42);
  });
});