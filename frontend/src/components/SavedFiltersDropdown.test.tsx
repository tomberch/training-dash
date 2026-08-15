import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SavedFiltersDropdown } from "./SavedFiltersDropdown";
import * as api from "../api";

// Mock the API
vi.mock("../api", async () => {
  const actual = await vi.importActual("../api");
  return {
    ...actual,
    fetchSavedFilters: vi.fn(),
  };
});

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe("SavedFiltersDropdown", () => {
  const mockFilters: api.SavedFilter[] = [
    {
      id: 1,
      name: "High TSS",
      query_text: "tss > 100",
      description: null,
      is_default: false,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: 2,
      name: "This Week",
      query_text: "date >= START_OF_WEEK",
      description: null,
      is_default: true,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: 3,
      name: "Long Rides",
      query_text: "distance > 50km",
      description: null,
      is_default: false,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderDropdown() {
    return render(
      <MemoryRouter>
        <SavedFiltersDropdown />
      </MemoryRouter>
    );
  }

  describe("rendering", () => {
    it("renders the trigger button", () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue([]);
      renderDropdown();
      expect(screen.getByRole("button", { name: /quick filter/i })).toBeInTheDocument();
    });

    it("dropdown is closed by default", () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue([]);
      renderDropdown();
      expect(screen.queryByText("Loading filters...")).not.toBeInTheDocument();
    });
  });

  describe("opening dropdown", () => {
    it("fetches filters when opened", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(api.fetchSavedFilters).toHaveBeenCalled();
      });
    });

    it("shows loading state while fetching", async () => {
      vi.mocked(api.fetchSavedFilters).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockFilters), 100))
      );
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      expect(screen.getByText("Loading filters...")).toBeInTheDocument();
    });

    it("shows filters after loading", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("High TSS")).toBeInTheDocument();
        expect(screen.getByText("This Week")).toBeInTheDocument();
        expect(screen.getByText("Long Rides")).toBeInTheDocument();
      });
    });

    it("shows empty state when no filters exist", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue([]);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("No saved filters yet.")).toBeInTheDocument();
      });
    });

    it("shows 'Create your first filter' link when empty", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue([]);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("Create your first filter")).toBeInTheDocument();
      });
    });
  });

  describe("filter selection", () => {
    it("navigates to query page with filter query when clicked", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("High TSS")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("High TSS"));

      expect(mockNavigate).toHaveBeenCalledWith("/query?q=tss%20%3E%20100");
    });

    it("URL-encodes special characters in query", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("This Week")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("This Week"));

      expect(mockNavigate).toHaveBeenCalledWith("/query?q=date%20%3E%3D%20START_OF_WEEK");
    });

    it("closes dropdown after selection", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("High TSS")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("High TSS"));

      await waitFor(() => {
        expect(screen.queryByText("High TSS")).not.toBeInTheDocument();
      });
    });
  });

  describe("Open Query Page link", () => {
    it("navigates to query page when clicked", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("Open Query Page")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Open Query Page"));

      expect(mockNavigate).toHaveBeenCalledWith("/query");
    });
  });

  describe("filter sorting", () => {
    it("shows default filter first", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        const buttons = screen.getAllByRole("button");
        const filterButtons = buttons.filter(
          (b) => b.textContent?.includes("TSS") || b.textContent?.includes("Week") || b.textContent?.includes("Rides")
        );
        // Default filter "This Week" should be first
        expect(filterButtons[0].textContent).toContain("This Week");
      });
    });
  });

  describe("closing behavior", () => {
    it("closes on Escape key", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("High TSS")).toBeInTheDocument();
      });

      fireEvent.keyDown(document, { key: "Escape" });

      await waitFor(() => {
        expect(screen.queryByText("High TSS")).not.toBeInTheDocument();
      });
    });

    it("toggles closed when clicking trigger again", async () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue(mockFilters);
      renderDropdown();

      const trigger = screen.getByRole("button", { name: /quick filter/i });

      fireEvent.click(trigger);

      await waitFor(() => {
        expect(screen.getByText("High TSS")).toBeInTheDocument();
      });

      fireEvent.click(trigger);

      await waitFor(() => {
        expect(screen.queryByText("High TSS")).not.toBeInTheDocument();
      });
    });
  });

  describe("error handling", () => {
    it("shows empty state on fetch error", async () => {
      vi.mocked(api.fetchSavedFilters).mockRejectedValue(new Error("Network error"));
      renderDropdown();

      fireEvent.click(screen.getByRole("button", { name: /quick filter/i }));

      await waitFor(() => {
        expect(screen.getByText("No saved filters yet.")).toBeInTheDocument();
      });
    });
  });

  describe("accessibility", () => {
    it("has aria-expanded attribute", () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue([]);
      renderDropdown();

      const trigger = screen.getByRole("button", { name: /quick filter/i });
      expect(trigger).toHaveAttribute("aria-expanded", "false");

      fireEvent.click(trigger);
      expect(trigger).toHaveAttribute("aria-expanded", "true");
    });

    it("has aria-haspopup attribute", () => {
      vi.mocked(api.fetchSavedFilters).mockResolvedValue([]);
      renderDropdown();

      const trigger = screen.getByRole("button", { name: /quick filter/i });
      expect(trigger).toHaveAttribute("aria-haspopup", "listbox");
    });
  });
});
