import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SuggestionsPage } from "./SuggestionsPage";

vi.mock("@/api/suggestions", () => ({
  fetchSuggestions: vi.fn(),
  approveSuggestion: vi.fn(),
  dismissSuggestion: vi.fn(),
  dismissAllSuggestions: vi.fn(),
}));

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Polyline: () => null,
  useMap: () => ({ fitBounds: () => null }),
}));

vi.mock("leaflet", () => ({
  default: { latLngBounds: () => ({}), latLng: () => ({}) },
}));

vi.mock("sonner", () => ({ toast: vi.fn() }));

import {
  fetchSuggestions,
  approveSuggestion,
  dismissSuggestion,
  dismissAllSuggestions,
} from "@/api/suggestions";
import type { PaginatedSuggestions, SegmentSuggestion } from "@/api/suggestions";

const mockFetch = vi.mocked(fetchSuggestions);
const mockApprove = vi.mocked(approveSuggestion);
const mockDismiss = vi.mocked(dismissSuggestion);
const mockDismissAll = vi.mocked(dismissAllSuggestions);

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const mockSuggestion: SegmentSuggestion = {
  id: "sug-1",
  segment_id: "seg-1",
  segment_type: "climb",
  climb_category: "2",
  distance_m: 12400,
  elevation_gain_m: 927,
  avg_grade_pct: 7.5,
  max_grade_pct: 12.1,
  repetition_count: 5,
  first_ridden_at: "2024-06-15T00:00:00Z",
  last_ridden_at: "2024-08-10T00:00:00Z",
  expires_at: null,
  polyline: "",
  elevation_profile: [
    { distance_m: 0, elevation_m: 800, grade_pct: 6.0 },
    { distance_m: 6200, elevation_m: 1172, grade_pct: 9.0 },
    { distance_m: 12400, elevation_m: 1727, grade_pct: 9.0 },
  ],
  start_point: { lat: 43.7, lng: 7.3 },
  end_point: { lat: 43.8, lng: 7.4 },
};

function paginated(items: SegmentSuggestion[], total?: number): PaginatedSuggestions {
  return {
    items,
    meta: {
      total: total ?? items.length,
      page: 1,
      per_page: 20,
      total_pages: 1,
    },
  };
}

describe("SuggestionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders suggestion cards", async () => {
    mockFetch.mockResolvedValue(paginated([mockSuggestion]));

    renderWithRouter(<SuggestionsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Segment Suggestions")).toBeInTheDocument();
      expect(screen.getByText("Climbs detected on your rides")).toBeInTheDocument();
      expect(screen.getByText("5× ridden")).toBeInTheDocument();
      expect(screen.getByText("Dismiss All")).toBeInTheDocument();
    });
  });

  it("renders empty state when no suggestions", async () => {
    mockFetch.mockResolvedValue(paginated([]));

    renderWithRouter(<SuggestionsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("No suggestions — keep riding!")).toBeInTheDocument();
    });
  });

  it("renders error state when fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("Network down"));

    renderWithRouter(<SuggestionsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Network down")).toBeInTheDocument();
    });
  });

  it("opens naming modal and approves on Save", async () => {
    mockFetch.mockResolvedValue(paginated([mockSuggestion]));
    mockApprove.mockResolvedValue({ id: "seg-1", name: "My Climb" });

    renderWithRouter(<SuggestionsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("5× ridden")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.getByText("Name your segment")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Segment name"), {
      target: { value: "My Climb" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Segment" }));

    await waitFor(() => {
      expect(mockApprove).toHaveBeenCalledWith("sug-1", "My Climb");
    });
  });

  it("dismisses a single suggestion", async () => {
    mockFetch.mockResolvedValue(paginated([mockSuggestion]));
    mockDismiss.mockResolvedValue(undefined);

    renderWithRouter(<SuggestionsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("5× ridden")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));

    await waitFor(() => {
      expect(mockDismiss).toHaveBeenCalledWith("sug-1");
    });
  });

  it("dismisses all suggestions with confirmation", async () => {
    mockFetch.mockResolvedValue(paginated([mockSuggestion]));
    mockDismissAll.mockResolvedValue(undefined);

    renderWithRouter(<SuggestionsPage unitSystem="metric" />);

    await waitFor(() => {
      expect(screen.getByText("Dismiss All")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Dismiss All" }));

    await waitFor(() => {
      expect(screen.getByText("Dismiss all suggestions?")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Dismiss All" }));

    await waitFor(() => {
      expect(mockDismissAll).toHaveBeenCalled();
    });
  });
});
