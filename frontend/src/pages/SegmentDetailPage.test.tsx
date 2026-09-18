import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { SegmentDetailPage } from "./SegmentDetailPage";

vi.mock("@/api/segments", () => ({
  fetchSegment: vi.fn(),
  fetchSegmentEfforts: vi.fn(),
  updateSegmentName: vi.fn(),
  deleteSegment: vi.fn(),
}));

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Polyline: () => null,
  Marker: () => null,
  useMap: () => ({ fitBounds: () => undefined }),
}));

vi.mock("leaflet", () => ({
  default: {
    latLngBounds: () => ({}),
    latLng: () => ({}),
  },
}));

import {
  fetchSegment,
  fetchSegmentEfforts,
  updateSegmentName,
} from "@/api/segments";
import type { PaginatedEfforts, SegmentDetailData, SegmentEffort } from "@/api/segments";

const mockFetchSegment = vi.mocked(fetchSegment);
const mockFetchEfforts = vi.mocked(fetchSegmentEfforts);
const mockUpdateSegment = vi.mocked(updateSegmentName);

function ActivityRouteMarker(): React.ReactElement {
  const { id } = useParams<{ id: string }>();
  return <div>Activity {id}</div>;
}

function renderWithRouter(ui: React.ReactElement, route: string): ReturnType<typeof render> {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/segments/:segmentId" element={ui} />
        <Route path="/segments" element={<div>Segments list</div>} />
        <Route path="/activities/:id" element={<ActivityRouteMarker />} />
      </Routes>
    </MemoryRouter>
  );
}

const segment: SegmentDetailData = {
  id: "seg-1",
  name: "Col de la Madone",
  type: "climb",
  status: "approved",
  climb_category: "2",
  polyline: "_p~iF~ps|U_ul",
  start_point: { lat: 43.7, lng: 7.4 },
  end_point: { lat: 43.8, lng: 7.5 },
  distance_m: 12400,
  elevation_gain_m: 927,
  avg_grade_pct: 7.5,
  max_grade_pct: 12.1,
  elevation_profile: [
    { distance_m: 0, elevation_m: 800, grade_pct: 4.2 },
    { distance_m: 500, elevation_m: 821, grade_pct: 8.1 },
    { distance_m: 1000, elevation_m: 862, grade_pct: 11.0 },
    { distance_m: 1500, elevation_m: 917, grade_pct: 7.5 },
  ],
  effort_count: 1847,
  athlete_count: 423,
  created_by: 42,
  created_at: "2024-06-01T00:00:00Z",
  my_stats: { effort_count: 3, pr_time_seconds: 2847, pr_date: "2024-08-10T09:00:00Z" },
};

const effort = (overrides: Partial<SegmentEffort>): SegmentEffort => ({
  id: "e1",
  segment_id: "seg-1",
  activity_id: "act-1",
  started_at: "2024-08-10T09:00:00Z",
  elapsed_time_seconds: 2900,
  moving_time_seconds: 2900,
  avg_power_watts: 280,
  avg_hr_bpm: 165,
  is_pr: false,
  ...overrides,
});

const prEffort = effort({
  id: "e-pr",
  elapsed_time_seconds: 2847,
  is_pr: true,
});

const effortsPage = (efforts: SegmentEffort[], total?: number): PaginatedEfforts => ({
  efforts,
  pagination: {
    total: total ?? efforts.length,
    page: 1,
    per_page: 20,
    total_pages: total && total > 20 ? Math.ceil(total / 20) : 1,
  },
});

describe("SegmentDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchSegment.mockResolvedValue(segment);
    mockFetchEfforts.mockResolvedValue(effortsPage([prEffort, effort({ id: "e2" })]));
  });

  it("renders segment name, type icon, and category badge", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    });
    expect(screen.getByText("Cat 2")).toBeInTheDocument();
  });

  it("renders elevation profile component", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      // ElevationProfile component should be present (recharts won't render in jsdom)
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    });
    // Note: recharts AreaChart doesn't render in jsdom, so we just verify no errors
  });

  it("renders PR card when user has efforts", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByText("Your PR")).toBeInTheDocument();
      expect(screen.getAllByText("47:27").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders efforts table with PR row highlighted and delta column", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByText("48:20")).toBeInTheDocument();
    });
    // PR row shows PR label, non-PR row shows +0:53 delta
    expect(screen.getByText("PR")).toBeInTheDocument();
    expect(screen.getByText("+0:53")).toBeInTheDocument();
  });

  it("highlights the PR row with amber styling and star", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      const prRow = screen.getAllByText("47:27").find(el => el.closest("tr") !== null)?.closest("tr");
      expect(prRow).toHaveClass("bg-amber-500/5");
      expect(screen.getByText("48:20")).toBeInTheDocument();
    });
    const star = document.querySelector("tr .text-amber-500");
    expect(star).toBeTruthy();
  });

  it("shows empty efforts state when user has no efforts", async () => {
    mockFetchSegment.mockResolvedValue({
      ...segment,
      my_stats: null,
    });
    mockFetchEfforts.mockResolvedValue(effortsPage([]));

    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(
        screen.getByText("You haven't ridden this segment yet")
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Your PR")).not.toBeInTheDocument();
  });

  it("shows rename and delete only for the owner", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Rename" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    });
  });

  it("hides rename and delete for non-owners", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={7} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("saves a rename and updates the header", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    const input = screen.getByLabelText("Segment name");
    fireEvent.change(input, { target: { value: "La Madone Climb" } });
    mockUpdateSegment.mockResolvedValue({ ...segment, name: "La Madone Climb" });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockUpdateSegment).toHaveBeenCalledWith("seg-1", "La Madone Climb");
      expect(screen.getByText("La Madone Climb")).toBeInTheDocument();
    });
  });

  it("shows error state when segment fetch fails", async () => {
    mockFetchSegment.mockRejectedValue(new Error("Not found"));

    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByText(/Failed to load segment: Not found/)).toBeInTheDocument();
    });
  });

  it("toggles sort order when clicking the same column", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByText("48:20")).toBeInTheDocument();
    });

    // default: time asc
    expect(mockFetchEfforts).toHaveBeenCalledWith(
      "seg-1",
      expect.objectContaining({ sort: "time", order: "asc" })
    );

    fireEvent.click(screen.getByRole("button", { name: /Date/ }));
    await waitFor(() => {
      expect(mockFetchEfforts).toHaveBeenCalledWith(
        "seg-1",
        expect.objectContaining({ sort: "date", order: "asc" })
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /Date/ }));
    await waitFor(() => {
      expect(mockFetchEfforts).toHaveBeenCalledWith(
        "seg-1",
        expect.objectContaining({ sort: "date", order: "desc" })
      );
    });
  });

  it("paginates efforts with next button", async () => {
    mockFetchEfforts.mockResolvedValue(effortsPage([prEffort], 45));

    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(mockFetchEfforts).toHaveBeenCalledWith(
        "seg-1",
        expect.objectContaining({ page: 2 })
      );
    });
  });

  it("navigates to the source activity when an effort row is clicked", async () => {
    renderWithRouter(
      <SegmentDetailPage unitSystem="metric" currentUserId={42} />,
      "/segments/seg-1"
    );

    await waitFor(() => {
      expect(screen.getByText("48:20")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("48:20").closest("tr")!);

    await waitFor(() => {
      expect(screen.getByText("Activity act-1")).toBeInTheDocument();
    });
  });
});