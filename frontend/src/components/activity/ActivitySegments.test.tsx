import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ActivitySegmentsSection, ActivitySegmentsCard, SuggestionInlineCard } from "./ActivitySegments";
import type { ActivitySegments, ActivitySegmentEffort } from "@/api/segments";
import type { SegmentSuggestion } from "@/api/suggestions";

vi.mock("@/api/suggestions", () => ({
  approveSuggestion: vi.fn(),
  dismissSuggestion: vi.fn(),
}));

vi.mock("@/api/activities", () => ({
  fetchActivityRecords: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: vi.fn() }));

import { approveSuggestion, dismissSuggestion } from "@/api/suggestions";
import { fetchActivityRecords } from "@/api/activities";

const mockApprove = vi.mocked(approveSuggestion);
const mockDismiss = vi.mocked(dismissSuggestion);
const mockRecords = vi.mocked(fetchActivityRecords);

function makeEffort(overrides: Partial<ActivitySegmentEffort> = {}): ActivitySegmentEffort {
  return {
    id: "e1",
    segment_id: "seg-1",
    segment_name: "Col de la Madone",
    segment_type: "climb",
    climb_category: "1",
    distance_m: 12400,
    elapsed_time_seconds: 2723,
    moving_time_seconds: 2700,
    avg_power_watts: 285,
    avg_hr_bpm: 168,
    is_pr: true,
    delta_to_pr_seconds: 0,
    start_index: 100,
    end_index: 500,
    ...overrides,
  };
}

function makeSuggestion(overrides: Partial<SegmentSuggestion> = {}): SegmentSuggestion {
  return {
    id: "sug-1",
    segment_id: "seg-2",
    segment_type: "climb",
    climb_category: "2",
    distance_m: 4200,
    elevation_gain_m: 310,
    avg_grade_pct: 7.4,
    max_grade_pct: 11.2,
    repetition_count: 5,
    first_ridden_at: "2024-06-15T00:00:00Z",
    last_ridden_at: "2024-08-10T00:00:00Z",
    expires_at: null,
    polyline: "",
    elevation_profile: [
      { distance_m: 0, elevation_m: 700, grade_pct: 6.0 },
      { distance_m: 2100, elevation_m: 826, grade_pct: 9.0 },
      { distance_m: 4200, elevation_m: 1010, grade_pct: 7.4 },
    ],
    start_point: { lat: 43.7, lng: 7.3 },
    end_point: { lat: 43.8, lng: 7.4 },
    source_activity_id: "act-1",
    ...overrides,
  };
}

describe("ActivitySegmentsCard", () => {
  it("renders efforts with name, category, and time", () => {
    render(
      <MemoryRouter>
        <ActivitySegmentsCard efforts={[makeEffort()]} />
      </MemoryRouter>
    );
    expect(screen.getByText("Col de la Madone")).toBeInTheDocument();
    expect(screen.getByLabelText("Personal record")).toBeInTheDocument();
  });

  it("renders empty state when no efforts", () => {
    render(
      <MemoryRouter>
        <ActivitySegmentsCard efforts={[]} />
      </MemoryRouter>
    );
    expect(screen.getByText("No segments crossed on this ride.")).toBeInTheDocument();
  });

  it("links to segment detail", () => {
    render(
      <MemoryRouter>
        <ActivitySegmentsCard efforts={[makeEffort()]} />
      </MemoryRouter>
    );
    const link = screen.getByText("Col de la Madone").closest("a");
    expect(link).toHaveAttribute("href", "/segments/seg-1");
  });
});

describe("SuggestionInlineCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders suggestion details and actions", () => {
    render(
      <MemoryRouter>
        <SuggestionInlineCard
          suggestion={makeSuggestion()}
          unitSystem="metric"
          onDismissed={vi.fn()}
          onApproved={vi.fn()}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("Climb Detected")).toBeInTheDocument();
    expect(screen.getByText("5× ridden")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save as Segment" })).toBeInTheDocument();
  });

  it("opens naming dialog and approves", async () => {
    mockApprove.mockResolvedValue({ id: "seg-2", name: "My Climb" });
    mockRecords.mockResolvedValue({
      features: Array.from({ length: 5 }, (_, i) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [7.3, 43.7 + i * 0.001] },
        properties: {
          timestamp: `2026-09-20T10:0${i}:00Z`,
          distance_m: i * 111,
          hr_bpm: null,
          power_w: null,
          speed_mps: null,
          altitude_m: 800 + i * 3,
          cadence_rpm: null,
        },
      })),
    } as never);
    const onApproved = vi.fn();
    render(
      <MemoryRouter>
        <SuggestionInlineCard
          suggestion={makeSuggestion()}
          unitSystem="metric"
          onDismissed={vi.fn()}
          onApproved={onApproved}
        />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Save as Segment" }));
    await waitFor(() => expect(screen.getByText("Name your segment")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Segment name"), { target: { value: "My Climb" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Segment" }));

    await waitFor(() =>
      expect(mockApprove).toHaveBeenCalledWith("sug-1", "My Climb", {
        start_index: 0,
        end_index: 4,
      })
    );
  });

  it("dismisses the suggestion", async () => {
    mockDismiss.mockResolvedValue(undefined);
    const onDismissed = vi.fn();
    render(
      <MemoryRouter>
        <SuggestionInlineCard
          suggestion={makeSuggestion()}
          unitSystem="metric"
          onDismissed={onDismissed}
          onApproved={vi.fn()}
        />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));

    await waitFor(() => expect(mockDismiss).toHaveBeenCalledWith("sug-1"));
  });
});

describe("ActivitySegmentsSection", () => {
  it("renders empty segments card when no efforts and no suggestion", () => {
    const data: ActivitySegments = { efforts: [], suggestion: null };
    render(
      <MemoryRouter>
        <ActivitySegmentsSection
          data={data}
          loading={false}
          unitSystem="metric"
          onSuggestionChange={vi.fn()}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("No segments crossed on this ride.")).toBeInTheDocument();
  });

  it("renders suggestion card when suggestion present", () => {
    const data: ActivitySegments = { efforts: [], suggestion: makeSuggestion() };
    render(
      <MemoryRouter>
        <ActivitySegmentsSection
          data={data}
          loading={false}
          unitSystem="metric"
          onSuggestionChange={vi.fn()}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("Climb Detected")).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    render(
      <MemoryRouter>
        <ActivitySegmentsSection
          data={null}
          loading={true}
          unitSystem="metric"
          onSuggestionChange={vi.fn()}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("Segments")).toBeInTheDocument();
  });
});
