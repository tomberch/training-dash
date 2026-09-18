import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SegmentsPage } from "./SegmentsPage";

vi.mock("@/api/segments", () => ({
  fetchSegments: vi.fn(),
}));

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Polyline: () => null,
  Popup: () => null,
  useMap: () => null,
  useMapEvents: () => null,
}));

vi.mock("leaflet", () => ({
  default: {
    latLngBounds: () => ({}),
    latLng: () => ({}),
  },
}));

import { fetchSegments } from "@/api/segments";
import type { PaginatedSegments, SegmentSummary } from "@/api/segments";

const mockFetchSegments = vi.mocked(fetchSegments);

function renderWithRouter(ui: React.ReactElement, initialEntries = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
  );
}

const mockSegment: SegmentSummary = {
  id: "seg-1",
  name: "Col de la Madone",
  type: "climb",
  climb_category: "2",
  distance_m: 12400,
  elevation_gain_m: 927,
  avg_grade_pct: 7.5,
  effort_count: 1847,
  athlete_count: 423,
};

const mockSprint: SegmentSummary = {
  id: "seg-2",
  name: "Village Sprint",
  type: "sprint",
  climb_category: null,
  distance_m: 400,
  elevation_gain_m: 3,
  avg_grade_pct: 0.8,
  effort_count: 12,
  athlete_count: 5,
};

function paginated(segments: SegmentSummary[], total?: number): PaginatedSegments {
  return {
    segments,
    pagination: {
      total: total ?? segments.length,
      page: 1,
      per_page: 20,
      total_pages: total && total > 20 ? Math.ceil(total / 20) : 1,
    },
  };
}

describe("SegmentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders segment list with segment cards", async () => {
    mockFetchSegments.mockResolvedValue(paginated([mockSegment, mockSprint]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
      expect(screen.getByText("Village Sprint")).toBeInTheDocument();
    });
  });

  it("renders header and subtitle", async () => {
    mockFetchSegments.mockResolvedValue(paginated([]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Segments")).toBeInTheDocument();
      expect(screen.getByText("Explore climbs and segments")).toBeInTheDocument();
    });
  });

  it("renders empty state when no segments", async () => {
    mockFetchSegments.mockResolvedValue(paginated([]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("No segments found")).toBeInTheDocument();
    });
  });

  it("renders error state when fetch fails", async () => {
    mockFetchSegments.mockRejectedValue(new Error("Network down"));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load segments: Network down/)).toBeInTheDocument();
    });
  });

  it("filters by type when type button clicked", async () => {
    mockFetchSegments.mockResolvedValue(paginated([mockSegment]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    });
    expect(mockFetchSegments).toHaveBeenCalledWith(
      expect.objectContaining({ type: undefined })
    );

    fireEvent.click(screen.getByRole("button", { name: "Climbs" }));

    await waitFor(() => {
      expect(mockFetchSegments).toHaveBeenCalledWith(
        expect.objectContaining({ type: "climb" })
      );
    });
  });

  it("shows category filter only for climbs and toggles categories", async () => {
    mockFetchSegments.mockResolvedValue(paginated([mockSegment]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    });

    // Categories hidden when type is "all"
    expect(screen.queryByRole("button", { name: "Cat 1" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Climbs" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Cat 1" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Cat 1" }));

    await waitFor(() => {
      expect(mockFetchSegments).toHaveBeenCalledWith(
        expect.objectContaining({ type: "climb", category: ["1"] })
      );
    });
  });

  it("searches by name on submit", async () => {
    mockFetchSegments.mockResolvedValue(paginated([]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(mockFetchSegments).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByLabelText("Search segments"), {
      target: { value: "madone" },
    });
    fireEvent.submit(screen.getByLabelText("Search segments"));

    await waitFor(() => {
      expect(mockFetchSegments).toHaveBeenCalledWith(
        expect.objectContaining({ q: "madone" })
      );
    });
  });

  it("shows pagination controls and navigates pages", async () => {
    mockFetchSegments.mockResolvedValue(paginated([mockSegment], 45));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(
        screen.getByText((_, el) =>
          el?.textContent === "Page 1 of 3 · 45 segments"
        )
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(mockFetchSegments).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2 })
      );
    });
  });

  it("navigates to segment detail on card click", async () => {
    mockFetchSegments.mockResolvedValue(paginated([mockSegment]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    });

    const link = screen.getByText("Col de la Madone").closest("a");
    expect(link).toHaveAttribute("href", "/segments/seg-1");
  });

  it("requests polylines when map view selected", async () => {
    mockFetchSegments.mockResolvedValue(paginated([mockSegment]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: "map" }));

    await waitFor(() => {
      expect(mockFetchSegments).toHaveBeenCalledWith(
        expect.objectContaining({ with_polyline: true })
      );
    });
  });

  it("shows athlete count alongside effort count", async () => {
    mockFetchSegments.mockResolvedValue(paginated([mockSegment]));

    renderWithRouter(<SegmentsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(
        screen.getByText((_, el) =>
          el?.textContent === "1,847 efforts · 423 athletes"
        )
      ).toBeInTheDocument();
    });
  });
});