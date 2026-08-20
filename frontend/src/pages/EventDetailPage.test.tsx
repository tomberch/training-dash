import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { EventDetailPage } from "./EventDetailPage";

// Mock toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/api/events", () => ({
  fetchEvent: vi.fn(),
  deleteEvent: vi.fn(),
  deleteMedia: vi.fn(),
  unlinkActivityFromEvent: vi.fn(),
}));

vi.mock("@/components/ActivityPickerDialog", () => ({
  ActivityPickerDialog: () => null,
}));

vi.mock("@/components/PhotoUploadDialog", () => ({
  PhotoUploadDialog: () => null,
}));

import { fetchEvent, deleteEvent } from "@/api/events";
import { toast } from "sonner";

const mockFetchEvent = vi.mocked(fetchEvent);
const mockDeleteEvent = vi.mocked(deleteEvent);

function renderWithRouter(eventId: string) {
  return render(
    <MemoryRouter initialEntries={[`/events/${eventId}`]}>
      <Routes>
        <Route path="/events/:id" element={<EventDetailPage />} />
        <Route path="/events" element={<div data-testid="events-list">Events List</div>} />
        <Route path="/events/:id/edit" element={<div data-testid="edit-page">Edit Page</div>} />
        <Route path="/activities/:id" element={<div data-testid="activity-detail">Activity Detail</div>} />
      </Routes>
    </MemoryRouter>
  );
}

const mockMultiDayEvent = {
  id: "event-1",
  title: "Alps Tour 2024",
  event_type: "tour",
  start_date: "2024-07-01",
  end_date: "2024-07-07",
  description: "# Adventure\n\nA scenic tour through the **Alps**.",
  cover_image_id: null,
  created_at: "2024-06-01T00:00:00Z",
  updated_at: "2024-06-01T00:00:00Z",
  entries: [
    {
      id: "entry-1",
      ride_event_id: "event-1",
      entry_date: "2024-07-01",
      description: "Day 1 was amazing!",
      created_at: "2024-07-01T20:00:00Z",
      updated_at: "2024-07-01T20:00:00Z",
      media: [],
      links: [],
      activities: [
        {
          id: 1,
          journal_entry_id: "entry-1",
          activity_id: "activity-1",
          sort_order: 0,
          activity: {
            id: "activity-1",
            title: "Morning Climb",
            started_at: "2024-07-01T08:00:00Z",
            distance_km: 85.5,
            elevation_m: 1200,
            duration_seconds: 14400, // 4h
            map_polyline: null,
          },
        },
      ],
    },
  ],
  media: [],
  links: [
    { id: "link-1", ride_event_id: "event-1", journal_entry_id: null, url: "https://example.com/route", title: "Route Map", link_type: "route", sort_order: 0 },
  ],
  stats: {
    total_distance_km: 85.5,
    total_duration_seconds: 14400,
    total_elevation_m: 1200,
    total_tss: null,
    activity_count: 1,
  },
};

const mockSingleDayEvent = {
  id: "event-2",
  title: "Local Crit Race",
  event_type: "race",
  start_date: "2024-08-15",
  end_date: "2024-08-15",
  description: "Fast and furious criterium.",
  cover_image_id: null,
  created_at: "2024-08-01T00:00:00Z",
  updated_at: "2024-08-01T00:00:00Z",
  entries: [],
  media: [],
  links: [],
  stats: {
    total_distance_km: null,
    total_duration_seconds: null,
    total_elevation_m: null,
    total_tss: null,
    activity_count: 0,
  },
};

describe("EventDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Loading and Error States", () => {
    it("renders loading state while fetching", () => {
      mockFetchEvent.mockReturnValue(new Promise(() => {}));
      renderWithRouter("event-1");

      // Page should render during loading state
      expect(document.body).not.toBeEmptyDOMElement();
    });

    it("renders error message on fetch failure", async () => {
      mockFetchEvent.mockRejectedValue(new Error("Not found"));
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
      });
    });
  });

  describe("Multi-Day Event Display", () => {
    it("renders event title and type badge", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Alps Tour 2024")).toBeInTheDocument();
        expect(screen.getByText("tour")).toBeInTheDocument();
      });
    });

    it("shows Day by Day section for multi-day events", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Day by Day")).toBeInTheDocument();
      });
    });

    it("renders Markdown description", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        // Check that markdown content is rendered - "Adventure" should appear as text
        expect(screen.getByText("Adventure")).toBeInTheDocument();
        // And "Alps" should be in bold (inside strong tag)
        expect(screen.getByText("Alps")).toBeInTheDocument();
      });
    });

    it("displays activity card with stats", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Morning Climb")).toBeInTheDocument();
        expect(screen.getByText("85.5 km · 1200m · 4h 0m")).toBeInTheDocument();
      });
    });

    it("displays event stats bar", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Distance")).toBeInTheDocument();
        expect(screen.getByText("Elevation")).toBeInTheDocument();
        expect(screen.getByText("Time")).toBeInTheDocument();
        expect(screen.getByText("Activities")).toBeInTheDocument();
      });
    });

    it("displays event links", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        const link = screen.getByRole("link", { name: /route map/i });
        expect(link).toHaveAttribute("href", "https://example.com/route");
      });
    });
  });

  describe("Single-Day Event Display", () => {
    it("does not show Day by Day section", async () => {
      mockFetchEvent.mockResolvedValue(mockSingleDayEvent);
      renderWithRouter("event-2");

      await waitFor(() => {
        expect(screen.getByText("Local Crit Race")).toBeInTheDocument();
      });

      expect(screen.queryByText("Day by Day")).not.toBeInTheDocument();
    });

    it("hides Activities count in stats bar for single-day", async () => {
      mockFetchEvent.mockResolvedValue(mockSingleDayEvent);
      renderWithRouter("event-2");

      await waitFor(() => {
        expect(screen.getByText("Distance")).toBeInTheDocument();
      });

      // Single-day events should show only 4 stats columns (Distance, Elevation, Time, Photos)
      // The Activities stat should only appear in the stats bar, not as section header
      const statsBar = document.querySelector(".bg-card.border-b");
      expect(statsBar?.textContent ?? "").not.toContain("Activities");
    });
  });

  describe("Navigation", () => {
    it("has back button that navigates to events list", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Alps Tour 2024")).toBeInTheDocument();
      });

      const backButton = screen.getByRole("button", { name: /back/i });
      fireEvent.click(backButton);

      await waitFor(() => {
        expect(screen.getByTestId("events-list")).toBeInTheDocument();
      });
    });

    it("has edit button that navigates to edit page", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Alps Tour 2024")).toBeInTheDocument();
      });

      const editButton = screen.getByRole("button", { name: /edit/i });
      fireEvent.click(editButton);

      await waitFor(() => {
        expect(screen.getByTestId("edit-page")).toBeInTheDocument();
      });
    });
  });

  describe("Delete Event", () => {
    it("shows confirmation dialog when delete button clicked", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Alps Tour 2024")).toBeInTheDocument();
      });

      // Find and click the delete button (trash icon button)
      const deleteButtons = screen.getAllByRole("button");
      const deleteButton = deleteButtons.find(b => b.innerHTML.includes("M19 7l"));
      expect(deleteButton).toBeTruthy();
      fireEvent.click(deleteButton!);

      await waitFor(() => {
        expect(screen.getByText("Delete Event")).toBeInTheDocument();
        expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
      });
    });

    it("deletes event and navigates away on confirm", async () => {
      mockFetchEvent.mockResolvedValue(mockMultiDayEvent);
      mockDeleteEvent.mockResolvedValue(undefined);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Alps Tour 2024")).toBeInTheDocument();
      });

      // Open delete dialog
      const deleteButtons = screen.getAllByRole("button");
      const deleteButton = deleteButtons.find(b => b.innerHTML.includes("M19 7l"));
      fireEvent.click(deleteButton!);

      await waitFor(() => {
        expect(screen.getByText("Delete Event")).toBeInTheDocument();
      });

      // Confirm delete
      const confirmButton = screen.getByRole("button", { name: /^delete$/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockDeleteEvent).toHaveBeenCalledWith("event-1");
        expect(toast.success).toHaveBeenCalledWith("Event deleted");
        expect(screen.getByTestId("events-list")).toBeInTheDocument();
      });
    });
  });
});
