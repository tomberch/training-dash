import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SavedFiltersPanel } from "./SavedFiltersPanel";
import * as api from "../api";

// Mock the API module
vi.mock("../api", async () => {
  const actual = await vi.importActual("../api");
  return {
    ...actual,
    fetchSavedFilters: vi.fn(),
    createSavedFilter: vi.fn(),
    updateSavedFilter: vi.fn(),
    deleteSavedFilter: vi.fn(),
    setDefaultFilter: vi.fn(),
    clearDefaultFilter: vi.fn(),
  };
});

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockFetchSavedFilters = vi.mocked(api.fetchSavedFilters);
const mockCreateSavedFilter = vi.mocked(api.createSavedFilter);
const mockDeleteSavedFilter = vi.mocked(api.deleteSavedFilter);
const mockSetDefaultFilter = vi.mocked(api.setDefaultFilter);
const mockClearDefaultFilter = vi.mocked(api.clearDefaultFilter);

const mockFilters: api.SavedFilter[] = [
  {
    id: 1,
    name: "High TSS",
    query_text: "tss > 100",
    description: "Activities with high stress",
    is_default: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Long Rides",
    query_text: "distance > 50km",
    description: null,
    is_default: false,
    created_at: "2024-01-02T00:00:00Z",
    updated_at: "2024-01-02T00:00:00Z",
  },
];

describe("SavedFiltersPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchSavedFilters.mockResolvedValue(mockFilters);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe("rendering", () => {
    it("renders saved filters button", async () => {
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });
    });

    it("renders save button", async () => {
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
      });
    });

    it("disables save button when query is empty", async () => {
      render(<SavedFiltersPanel currentQuery="" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
      });
    });

    it("shows filter count badge", async () => {
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText("2")).toBeInTheDocument();
      });
    });
  });

  describe("filters dropdown", () => {
    it("opens dropdown when clicking saved filters button", async () => {
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));

      expect(screen.getByText("High TSS")).toBeInTheDocument();
      expect(screen.getByText("Long Rides")).toBeInTheDocument();
    });

    it("shows filter descriptions", async () => {
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));

      expect(screen.getByText("Activities with high stress")).toBeInTheDocument();
    });

    it("shows default star indicator", async () => {
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));

      // The default filter should have a filled star
      const filterItems = screen.getAllByRole("button", { name: /set as default|remove default/i });
      expect(filterItems.length).toBeGreaterThan(0);
    });

    it("shows empty state when no filters", async () => {
      mockFetchSavedFilters.mockResolvedValueOnce([]);
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));

      expect(screen.getByText(/no saved filters yet/i)).toBeInTheDocument();
    });
  });

  describe("loading filter", () => {
    it("calls onLoadFilter when clicking a filter", async () => {
      const onLoadFilter = vi.fn();
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={onLoadFilter} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));
      await user.click(screen.getByText("High TSS"));

      expect(onLoadFilter).toHaveBeenCalledWith("tss > 100");
    });
  });

  describe("saving filter", () => {
    it("opens save dialog when clicking save button", async () => {
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /^save$/i })).toBeEnabled();
      });

      await user.click(screen.getByRole("button", { name: /^save$/i }));

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText(/save filter/i)).toBeInTheDocument();
    });

    it("shows current query in save dialog", async () => {
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /^save$/i })).toBeEnabled();
      });

      await user.click(screen.getByRole("button", { name: /^save$/i }));

      expect(screen.getByText("tss > 50")).toBeInTheDocument();
    });

    it("creates filter when submitting save dialog", async () => {
      mockCreateSavedFilter.mockResolvedValueOnce({
        id: 3,
        name: "New Filter",
        query_text: "tss > 50",
        description: "Test description",
        is_default: false,
        created_at: "2024-01-03T00:00:00Z",
        updated_at: "2024-01-03T00:00:00Z",
      });

      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /^save$/i })).toBeEnabled();
      });

      await user.click(screen.getByRole("button", { name: /^save$/i }));

      await user.type(screen.getByLabelText(/name/i), "New Filter");
      await user.type(screen.getByLabelText(/description/i), "Test description");
      await user.click(screen.getByRole("button", { name: /^save$/i }));

      await waitFor(() => {
        expect(mockCreateSavedFilter).toHaveBeenCalledWith({
          name: "New Filter",
          query_text: "tss > 50",
          description: "Test description",
          is_default: false,
        });
      });
    });
  });

  describe("deleting filter", () => {
    it("opens delete dialog when clicking delete button", async () => {
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));
      
      const deleteButtons = screen.getAllByTitle("Delete");
      await user.click(deleteButtons[0]);

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText(/delete filter/i)).toBeInTheDocument();
    });

    it("deletes filter when confirming", async () => {
      mockDeleteSavedFilter.mockResolvedValueOnce();
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));
      
      const deleteButtons = screen.getAllByTitle("Delete");
      await user.click(deleteButtons[0]);

      await user.click(screen.getByRole("button", { name: /^delete$/i }));

      await waitFor(() => {
        expect(mockDeleteSavedFilter).toHaveBeenCalledWith(1);
      });
    });
  });

  describe("default filter", () => {
    it("sets default filter when clicking star on non-default", async () => {
      mockSetDefaultFilter.mockResolvedValueOnce(mockFilters[1]);
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));
      
      // Click on the star for "Long Rides" which is not default
      const starButtons = screen.getAllByTitle(/set as default/i);
      await user.click(starButtons[0]);

      await waitFor(() => {
        expect(mockSetDefaultFilter).toHaveBeenCalledWith(2);
      });
    });

    it("clears default filter when clicking star on default", async () => {
      mockClearDefaultFilter.mockResolvedValueOnce();
      const user = userEvent.setup();
      render(<SavedFiltersPanel currentQuery="tss > 50" onLoadFilter={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /saved filters/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /saved filters/i }));
      
      // Click on the star for "High TSS" which is default
      const starButtons = screen.getAllByTitle(/remove default/i);
      await user.click(starButtons[0]);

      await waitFor(() => {
        expect(mockClearDefaultFilter).toHaveBeenCalled();
      });
    });
  });
});
