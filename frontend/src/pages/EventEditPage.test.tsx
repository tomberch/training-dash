import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { EventEditPage } from "./EventEditPage";

// Mock toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/api/events", () => ({
  fetchEvent: vi.fn(),
  updateEvent: vi.fn(),
  createJournalEntry: vi.fn(),
  updateJournalEntry: vi.fn(),
  deleteJournalEntry: vi.fn(),
  createEventLink: vi.fn(),
  deleteLink: vi.fn(),
  deleteMedia: vi.fn(),
  setEventCover: vi.fn(),
  unlinkActivityFromEvent: vi.fn(),
}));

vi.mock("@/components/ActivityPickerDialog", () => ({
  ActivityPickerDialog: () => null,
}));

vi.mock("@/components/PhotoUploadDialog", () => ({
  PhotoUploadDialog: () => null,
}));

import { fetchEvent } from "@/api/events";

const mockFetchEvent = vi.mocked(fetchEvent);

function renderWithRouter(eventId: string) {
  return render(
    <MemoryRouter initialEntries={[`/events/${eventId}/edit`]}>
      <Routes>
        <Route path="/events/:id/edit" element={<EventEditPage />} />
        <Route path="/events/:id" element={<div data-testid="detail-page">Detail Page</div>} />
        <Route path="/events" element={<div data-testid="events-list">Events List</div>} />
      </Routes>
    </MemoryRouter>
  );
}

const mockEvent = {
  id: "event-1",
  title: "Summer Tour 2024",
  event_type: "tour",
  start_date: "2024-07-01",
  end_date: "2024-07-07",
  description: "A great adventure",
  cover_image_id: null,
  created_at: "2024-06-01T00:00:00Z",
  updated_at: "2024-06-01T00:00:00Z",
  entries: [
    {
      id: "entry-1",
      ride_event_id: "event-1",
      entry_date: "2024-07-01",
      description: "Day 1 notes",
      created_at: "2024-07-01T20:00:00Z",
      updated_at: "2024-07-01T20:00:00Z",
      media: [],
      links: [],
      activities: [],
    },
  ],
  media: [
    {
      id: "photo-1",
      ride_event_id: "event-1",
      journal_entry_id: null,
      media_type: "photo" as const,
      storage_path: "/photos/1.jpg",
      thumbnail_path: "/photos/1_thumb.jpg",
      caption: null,
      sort_order: 0,
    },
  ],
  links: [
    {
      id: "link-1",
      ride_event_id: "event-1",
      journal_entry_id: null,
      url: "https://example.com",
      title: "Route Link",
      link_type: "route",
      sort_order: 0,
    },
  ],
  stats: {
    total_distance_km: 350,
    total_duration_seconds: 36000,
    total_elevation_m: 5000,
    total_tss: null,
    activity_count: 5,
  },
};

describe("EventEditPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Loading and Error States", () => {
    it("renders error message on fetch failure", async () => {
      mockFetchEvent.mockRejectedValue(new Error("Not found"));
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
      });
    });
  });

  describe("Event Display", () => {
    it("renders event title", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Summer Tour 2024")).toBeInTheDocument();
      });
    });

    it("displays Day by Day section header", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        // Multi-day event shows "Day by Day" section
        expect(screen.getByText("Day by Day")).toBeInTheDocument();
      });
    });

    it("displays existing links", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Route Link")).toBeInTheDocument();
      });
    });

    it("displays photo gallery with set-cover action", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        // Photo should be rendered
        const img = document.querySelector('img[src="/photos/1_thumb.jpg"]');
        expect(img).toBeInTheDocument();
      });
    });
  });

  describe("Navigation", () => {
    it("has Done button that navigates to detail page", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Summer Tour 2024")).toBeInTheDocument();
      });

      const doneButton = screen.getByRole("button", { name: /done/i });
      fireEvent.click(doneButton);

      await waitFor(() => {
        expect(screen.getByTestId("detail-page")).toBeInTheDocument();
      });
    });
  });

  describe("Edit Description", () => {
    it("shows description in edit mode", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        // The description should be displayed (might be in MDEditor)
        expect(screen.getByText("Event Description")).toBeInTheDocument();
      });
    });
  });

  describe("Add Journal Entry", () => {
    it("has add button in Day by Day section", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Day by Day")).toBeInTheDocument();
      });
      
      // There should be at least one plus icon button for adding entries
      const plusButtons = screen.getAllByRole("button").filter(b => 
        b.innerHTML.includes("M12 4v16m8-8H4")
      );
      expect(plusButtons.length).toBeGreaterThan(0);
    });
  });

  describe("Delete Journal Entry", () => {
    it("has delete button for journal entries", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        expect(screen.getByText("Day by Day")).toBeInTheDocument();
      });

      // Find delete button for the entry (trash icon in entry)
      // The entry section should have a delete button
      const entryDeleteButtons = screen.getAllByRole("button").filter(b => 
        b.innerHTML.includes("M19 7l")
      );
      
      // Should have at least one delete button (for the entry)
      expect(entryDeleteButtons.length).toBeGreaterThan(0);
    });
  });

  describe("Add Link", () => {
    it("shows Add Link button", async () => {
      mockFetchEvent.mockResolvedValue(mockEvent);
      renderWithRouter("event-1");

      await waitFor(() => {
        const addLinkButton = screen.getByRole("button", { name: /add link/i });
        expect(addLinkButton).toBeInTheDocument();
      });
    });
  });
});
