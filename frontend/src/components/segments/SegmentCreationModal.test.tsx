import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SegmentCreationModal } from "./SegmentCreationModal";
import type { GeoJSONFeatureCollection } from "@/api";

vi.mock("@/api/segments", () => ({
  createSegment: vi.fn(),
  SegmentDuplicateError: class extends Error {
    duplicateSegmentId: string;
    constructor(message: string, duplicateSegmentId: string) {
      super(message);
      this.duplicateSegmentId = duplicateSegmentId;
    }
  },
}));

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Polyline: () => null,
  Marker: () => null,
  useMap: () => ({ fitBounds: () => null }),
  useMapEvents: ({ click }: { click: (e: { latlng: { lat: number; lng: number } }) => void }) => {
    // capture the click handler for tests
    (globalThis as any).__mapClick = click;
    return null;
  },
}));

vi.mock("leaflet", () => ({
  default: {
    latLngBounds: () => ({}),
    latLng: () => ({}),
    divIcon: () => ({}),
  },
}));

vi.mock("sonner", () => ({ toast: vi.fn() }));

function feature(_index: number, lng: number, lat: number, altitude_m: number | null, distance_m: number) {
  return {
    type: "Feature" as const,
    geometry: altitude_m === null ? null : { type: "Point", coordinates: [lng, lat] },
    properties: {
      timestamp: "2024-01-01T00:00:00Z",
      distance_m,
      hr_bpm: null,
      power_w: null,
      speed_mps: null,
      altitude_m,
      cadence_rpm: null,
    },
  };
}

function makeGeojson(): GeoJSONFeatureCollection {
  return {
    type: "FeatureCollection",
    activity_id: "a1",
    features: [
      feature(0, 0, 0, 10, 0),
      feature(1, 0.001, 0.001, 11, 100),
      feature(2, 0.002, 0.002, 12, 200),
      feature(3, 0.003, 0.003, 13, 300),
      feature(4, 0.004, 0.004, 14, 400),
    ],
  };
}

const navigateMock = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

function renderModal() {
  return render(
    <MemoryRouter>
      <SegmentCreationModal
        open={true}
        onOpenChange={vi.fn()}
        activityId="a1"
        geojson={makeGeojson()}
        unitSystem="metric"
      />
    </MemoryRouter>
  );
}

describe("SegmentCreationModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete (globalThis as any).__mapClick;
  });

  it("renders the creation dialog with selection card", () => {
    renderModal();
    expect(screen.getAllByText("Create Segment").length).toBeGreaterThan(0);
    expect(screen.getByText("Selection")).toBeInTheDocument();
    expect(screen.getByText(/Start:/)).toBeInTheDocument();
    expect(screen.getByText(/End:/)).toBeInTheDocument();
  });

  it("create button is disabled until valid name and selection", () => {
    renderModal();
    const footerButton = screen.getAllByText("Create Segment").at(-1);
    expect(footerButton!.closest("button")).toBeDisabled();
  });

  it("computes preview when both points are selected", async () => {
    renderModal();
    const getClick = () => (globalThis as any).__mapClick as ((e: { latlng: { lat: number; lng: number } }) => void);
    act(() => getClick()({ latlng: { lat: 0, lng: 0 } }));
    await waitFor(() => expect(screen.getByText(/record #0/)).toBeInTheDocument());
    act(() => getClick()({ latlng: { lat: 0.003, lng: 0.003 } }));

    await waitFor(() => {
      expect(screen.getByText(/record #0/)).toBeInTheDocument();
      expect(screen.getByText(/record #3/)).toBeInTheDocument();
    });
  });
});
