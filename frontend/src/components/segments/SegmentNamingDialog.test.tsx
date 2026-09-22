/**
 * Tests for SegmentNamingDialog — naming plus endpoint adjustment.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SegmentNamingDialog } from "./SegmentNamingDialog";
import type { SegmentSuggestion } from "@/api/suggestions";

vi.mock("@/api/suggestions", () => ({
  approveSuggestion: vi.fn(),
}));

vi.mock("@/api/activities", () => ({
  fetchActivityRecords: vi.fn(),
}));

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) => (
    <div data-testid="map" style={style}>
      {children}
    </div>
  ),
  TileLayer: () => null,
  Polyline: () => null,
  Marker: () => null,
  useMapEvents: () => null,
  useMap: () => ({ fitBounds: () => null }),
}));

vi.mock("leaflet", () => ({
  default: {
    latLngBounds: () => ({}),
    latLng: () => ({}),
    divIcon: (opts: Record<string, unknown>) => opts,
  },
}));

vi.mock("sonner", () => ({ toast: vi.fn() }));

import { approveSuggestion } from "@/api/suggestions";
import { fetchActivityRecords } from "@/api/activities";
import type { GeoJSONFeatureCollection } from "@/api";

const mockApprove = vi.mocked(approveSuggestion);
const mockRecords = vi.mocked(fetchActivityRecords);

function geojson(n: number): GeoJSONFeatureCollection {
  return {
    type: "FeatureCollection",
    activity_id: "act-1",
    features: Array.from({ length: n }, (_, i) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [7.4 + i * 0.001, 46.9 + i * 0.001] },
      properties: {
        timestamp: `2026-09-20T10:${String(i).padStart(2, "0")}:00Z`,
        distance_m: i * 111,
        hr_bpm: null,
        power_w: null,
        speed_mps: null,
        altitude_m: 500 + i * 3,
        cadence_rpm: null,
      },
    })),
  };
}

const suggestion: SegmentSuggestion = {
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
  polyline: "_p~iF~ps|U_ulLnnqC",
  elevation_profile: [
    { distance_m: 0, elevation_m: 800, grade_pct: 6.0 },
    { distance_m: 6200, elevation_m: 1172, grade_pct: 9.0 },
  ],
  start_point: { lat: 46.9, lng: 7.4 },
  end_point: { lat: 46.95, lng: 7.45 },
  source_activity_id: "act-1",
};

function renderDialog(sug: SegmentSuggestion | null = suggestion) {
  return render(
    <MemoryRouter>
      <SegmentNamingDialog
        suggestion={sug}
        open={sug !== null}
        onOpenChange={() => {}}
        unitSystem="metric"
        onCreated={() => {}}
      />
    </MemoryRouter>
  );
}

describe("SegmentNamingDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRecords.mockResolvedValue(geojson(20) as never);
  });

  it("shows the interactive map with the source activity track", async () => {
    renderDialog();

    await waitFor(() => {
      expect(screen.getByTestId("map")).toBeInTheDocument();
    });
    expect(mockRecords).toHaveBeenCalledWith("act-1");
  });

  it("approves with the detected endpoints snapped to the track", async () => {
    mockApprove.mockResolvedValue({ id: "seg-1", name: "My Climb" });
    renderDialog();

    await waitFor(() => expect(screen.getByTestId("map")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Segment name"), { target: { value: "My Climb" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Segment" }));

    await waitFor(() => {
      // Default selection snaps to the suggestion's detected start/end
      // points (start 46.9 → index 0, end 46.95 → nearest is index 19)
      expect(mockApprove).toHaveBeenCalledWith("sug-1", "My Climb", {
        start_index: 0,
        end_index: 19,
      });
    });
  });

  it("renders fallback when suggestion has no source activity", async () => {
    renderDialog({ ...suggestion, source_activity_id: null });

    // Dialog still opens with the name input; no map fetch attempted
    expect(screen.getByLabelText("Segment name")).toBeInTheDocument();
    expect(mockRecords).not.toHaveBeenCalled();
  });
});