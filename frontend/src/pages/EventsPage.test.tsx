import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { EventsPage } from "./EventsPage";

vi.mock("@/api/events", () => ({
  fetchEvents: vi.fn(),
}));

import { fetchEvents } from "@/api/events";

const mockFetchEvents = vi.mocked(fetchEvents);

function renderWithRouter(ui: React.ReactElement, initialEntries = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
  );
}

const mockEvent = {
  id: "event-1",
  title: "Summer Tour 2024",
  event_type: "tour",
  start_date: "2024-07-01",
  end_date: "2024-07-07",
  description: "A week-long tour",
  cover_image_id: null,
  created_at: "2024-06-01T00:00:00Z",
  updated_at: "2024-06-01T00:00:00Z",
};

const mockSingleDayEvent = {
  id: "event-2",
  title: "Local Race",
  event_type: "race",
  start_date: "2024-08-15",
  end_date: "2024-08-15",
  description: null,
  cover_image_id: null,
  created_at: "2024-08-01T00:00:00Z",
  updated_at: "2024-08-01T00:00:00Z",
};

describe("EventsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state when no events", async () => {
    mockFetchEvents.mockResolvedValue({
      events: [],
      pagination: { total: 0, page: 1, per_page: 12, total_pages: 0 },
    });

    renderWithRouter(<EventsPage />);

    await waitFor(() => {
      expect(screen.getByText("No events yet")).toBeInTheDocument();
    });
  });

  it("renders events list with event cards", async () => {
    mockFetchEvents.mockResolvedValue({
      events: [mockEvent, mockSingleDayEvent],
      pagination: { total: 2, page: 1, per_page: 12, total_pages: 1 },
    });

    renderWithRouter(<EventsPage />);

    await waitFor(() => {
      expect(screen.getByText("Summer Tour 2024")).toBeInTheDocument();
      expect(screen.getByText("Local Race")).toBeInTheDocument();
    });
  });

  it("displays event type badges", async () => {
    mockFetchEvents.mockResolvedValue({
      events: [mockEvent, mockSingleDayEvent],
      pagination: { total: 2, page: 1, per_page: 12, total_pages: 1 },
    });

    renderWithRouter(<EventsPage />);

    await waitFor(() => {
      expect(screen.getByText("tour")).toBeInTheDocument();
      expect(screen.getByText("race")).toBeInTheDocument();
    });
  });

  it("filters events by type when filter button clicked", async () => {
    mockFetchEvents.mockResolvedValue({
      events: [mockEvent],
      pagination: { total: 1, page: 1, per_page: 12, total_pages: 1 },
    });

    renderWithRouter(<EventsPage />);

    await waitFor(() => {
      expect(screen.getByText("Summer Tour 2024")).toBeInTheDocument();
    });

    // Click the "Tour" filter button
    const tourFilter = screen.getByRole("button", { name: /tour/i });
    fireEvent.click(tourFilter);

    await waitFor(() => {
      expect(mockFetchEvents).toHaveBeenCalledWith(1, 12, "tour");
    });
  });

  it("shows All filter as active by default", async () => {
    mockFetchEvents.mockResolvedValue({
      events: [],
      pagination: { total: 0, page: 1, per_page: 12, total_pages: 0 },
    });

    renderWithRouter(<EventsPage />);

    await waitFor(() => {
      const allButton = screen.getByRole("button", { name: /all/i });
      // All button should have active styling (bg-primary)
      expect(allButton.className).toContain("bg-primary");
    });
  });

  it("resets to All filter when clicking All button", async () => {
    mockFetchEvents.mockResolvedValue({
      events: [mockEvent],
      pagination: { total: 1, page: 1, per_page: 12, total_pages: 1 },
    });

    renderWithRouter(<EventsPage />);

    await waitFor(() => {
      expect(screen.getByText("Summer Tour 2024")).toBeInTheDocument();
    });

    // Click tour filter first
    const tourFilter = screen.getByRole("button", { name: /^tour$/i });
    fireEvent.click(tourFilter);

    // Click All filter to reset
    const allFilter = screen.getByRole("button", { name: /^all$/i });
    fireEvent.click(allFilter);

    await waitFor(() => {
      // Should call with undefined event type (all)
      expect(mockFetchEvents).toHaveBeenLastCalledWith(1, 12, undefined);
    });
  });

  it("renders loading state while fetching", () => {
    // Never resolve the promise
    mockFetchEvents.mockReturnValue(new Promise(() => {}));

    renderWithRouter(<EventsPage />);

    // Page should render without error even during loading
    expect(screen.getByText("Events")).toBeInTheDocument();
  });

  it("renders error state on API failure", async () => {
    mockFetchEvents.mockRejectedValue(new Error("Network error"));

    renderWithRouter(<EventsPage />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });

  it("has a link to create new event", async () => {
    mockFetchEvents.mockResolvedValue({
      events: [],
      pagination: { total: 0, page: 1, per_page: 12, total_pages: 0 },
    });

    renderWithRouter(<EventsPage />);

    await waitFor(() => {
      const createButton = screen.getByText(/create.*event/i);
      expect(createButton).toBeInTheDocument();
    });
  });
});
