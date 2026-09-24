import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ActivitySegmentsSection, ActivitySegmentsCard } from "./ActivitySegments";
import type { ActivitySegments, ActivitySegmentEffort } from "@/api/segments";

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

describe("ActivitySegmentsSection", () => {
  it("renders empty segments card when no efforts", () => {
    const data: ActivitySegments = { efforts: [], suggestion: null };
    render(
      <MemoryRouter>
        <ActivitySegmentsSection
          data={data}
          loading={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("No segments crossed on this ride.")).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    render(
      <MemoryRouter>
        <ActivitySegmentsSection
          data={null}
          loading={true}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("Segments")).toBeInTheDocument();
  });
});
