import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryPage } from "./QueryPage";
import * as api from "../api";

// Mock the API module
vi.mock("../api", async () => {
  const actual = await vi.importActual("../api");
  return {
    ...actual,
    executeQuery: vi.fn(),
  };
});

const mockExecuteQuery = vi.mocked(api.executeQuery);

function renderQueryPage(initialRoute = "/query") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <QueryPage />
    </MemoryRouter>
  );
}

describe("QueryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe("rendering", () => {
    it("renders page header", () => {
      renderQueryPage();
      expect(screen.getByRole("heading", { name: /query/i })).toBeInTheDocument();
    });

    it("renders query input textarea", () => {
      renderQueryPage();
      expect(screen.getByPlaceholderText(/enter query/i)).toBeInTheDocument();
    });

    it("renders run query button", () => {
      renderQueryPage();
      expect(screen.getByRole("button", { name: /run query/i })).toBeInTheDocument();
    });

    it("shows empty state with example queries", () => {
      renderQueryPage();
      expect(screen.getByText(/enter a query to get started/i)).toBeInTheDocument();
      expect(screen.getByText(/tss > 100/)).toBeInTheDocument();
    });

    it("disables run button when query is empty", () => {
      renderQueryPage();
      const button = screen.getByRole("button", { name: /run query/i });
      expect(button).toBeDisabled();
    });
  });

  describe("query execution", () => {
    it("executes query on button click", async () => {
      mockExecuteQuery.mockResolvedValueOnce({
        type: "list",
        results: [],
        total: 0,
        page: 1,
        per_page: 20,
      });

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);
      const button = screen.getByRole("button", { name: /run query/i });

      await userEvent.type(textarea, "tss > 100");
      await userEvent.click(button);

      await waitFor(() => {
        expect(mockExecuteQuery).toHaveBeenCalledWith("tss > 100", 1, 20);
      });
    });

    it("executes query on Ctrl+Enter", async () => {
      mockExecuteQuery.mockResolvedValueOnce({
        type: "list",
        results: [],
        total: 0,
        page: 1,
        per_page: 20,
      });

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "tss > 100");
      fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });

      await waitFor(() => {
        expect(mockExecuteQuery).toHaveBeenCalledWith("tss > 100", 1, 20);
      });
    });

    it("shows loading state during query execution", async () => {
      let resolveQuery: (value: api.QueryResponse) => void;
      mockExecuteQuery.mockImplementationOnce(() => 
        new Promise((resolve) => { resolveQuery = resolve; })
      );

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);
      const button = screen.getByRole("button", { name: /run query/i });

      await userEvent.type(textarea, "tss > 100");
      await userEvent.click(button);

      expect(screen.getByRole("button", { name: /running/i })).toBeDisabled();

      // Resolve the query
      resolveQuery!({
        type: "list",
        results: [],
        total: 0,
        page: 1,
        per_page: 20,
      });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /run query/i })).toBeEnabled();
      });
    });
  });

  describe("list results", () => {
    it("displays list results with activity count", async () => {
      mockExecuteQuery.mockResolvedValueOnce({
        type: "list",
        results: [
          {
            id: "abc123",
            title: "Morning Ride",
            started_at: "2024-01-15T08:00:00Z",
            total_distance_m: 50000,
            moving_time_s: 5400,
            tss: 120,
          },
          {
            id: "def456",
            title: "Evening Ride",
            started_at: "2024-01-14T17:00:00Z",
            total_distance_m: 30000,
            moving_time_s: 3600,
            tss: 80,
          },
        ],
        total: 2,
        page: 1,
        per_page: 20,
      });

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "tss > 50");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText(/showing 2 of 2 activities/i)).toBeInTheDocument();
      });

      expect(screen.getByText("Morning Ride")).toBeInTheDocument();
      expect(screen.getByText("Evening Ride")).toBeInTheDocument();
    });

    it("shows no results message for empty list", async () => {
      mockExecuteQuery.mockResolvedValueOnce({
        type: "list",
        results: [],
        total: 0,
        page: 1,
        per_page: 20,
      });

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "tss > 9999");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText(/no activities match your query/i)).toBeInTheDocument();
      });
    });

    it("shows pagination for multiple pages", async () => {
      mockExecuteQuery.mockResolvedValueOnce({
        type: "list",
        results: Array(20).fill(null).map((_, i) => ({
          id: `id${i}`,
          title: `Activity ${i}`,
          started_at: "2024-01-15T08:00:00Z",
          total_distance_m: 50000,
          moving_time_s: 5400,
          tss: 100,
        })),
        total: 50,
        page: 1,
        per_page: 20,
      });

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "tss > 50");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();
      expect(screen.getByRole("button", { name: /next/i })).toBeEnabled();
    });
  });

  describe("scalar results", () => {
    it("displays scalar aggregation results", async () => {
      mockExecuteQuery.mockResolvedValueOnce({
        type: "scalar",
        results: {
          count_star: 42,
          avg_tss: 85.5,
          sum_distance_m: 1234567,
        },
      });

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "COUNT(*), AVG(tss), SUM(distance)");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText("42")).toBeInTheDocument();
      });
      expect(screen.getByText("85.5")).toBeInTheDocument();
      expect(screen.getByText(/1,234,567/)).toBeInTheDocument();
    });
  });

  describe("grouped results", () => {
    it("displays grouped aggregation results as table", async () => {
      mockExecuteQuery.mockResolvedValueOnce({
        type: "grouped",
        group_by: ["time_bucket"],
        results: [
          { time_bucket: "2024-01-01T00:00:00Z", count_star: 10, avg_tss: 75 },
          { time_bucket: "2024-02-01T00:00:00Z", count_star: 8, avg_tss: 82 },
        ],
      });

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "COUNT(*), AVG(tss) GROUP BY month");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText("Period")).toBeInTheDocument();
      });
      expect(screen.getByText("Count")).toBeInTheDocument();
      expect(screen.getByText("Avg Tss")).toBeInTheDocument();
      expect(screen.getByText("10")).toBeInTheDocument();
      expect(screen.getByText("8")).toBeInTheDocument();
    });
  });

  describe("error handling", () => {
    it("displays parse error with context", async () => {
      mockExecuteQuery.mockRejectedValueOnce(
        new api.QueryError({
          stage: "parse",
          message: "Unexpected token",
          line: 1,
          column: 5,
          context: "tss >> 100\n    ^",
        })
      );

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "tss >> 100");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText(/parse error/i)).toBeInTheDocument();
      });
      expect(screen.getByText("Unexpected token")).toBeInTheDocument();
      expect(screen.getByText(/line 1, column 5/i)).toBeInTheDocument();
    });

    it("displays validation error with field and suggestions", async () => {
      mockExecuteQuery.mockRejectedValueOnce(
        new api.QueryError({
          stage: "validation",
          message: "Unknown field 'tts'",
          field: "tts",
          suggestions: ["tss", "title"],
        })
      );

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "tts > 100");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText(/validation error/i)).toBeInTheDocument();
      });
      expect(screen.getByText("Unknown field 'tts'")).toBeInTheDocument();
      expect(screen.getByText(/did you mean/i)).toBeInTheDocument();
      expect(screen.getByText("tss")).toBeInTheDocument();
    });

    it("displays execution error", async () => {
      mockExecuteQuery.mockRejectedValueOnce(
        new api.QueryError({
          stage: "execution",
          message: "Database connection failed",
        })
      );

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "tss > 100");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText(/execution error/i)).toBeInTheDocument();
      });
      expect(screen.getByText("Database connection failed")).toBeInTheDocument();
    });

    it("handles generic errors", async () => {
      mockExecuteQuery.mockRejectedValueOnce(new Error("Network error"));

      renderQueryPage();
      const textarea = screen.getByPlaceholderText(/enter query/i);

      await userEvent.type(textarea, "tss > 100");
      await userEvent.click(screen.getByRole("button", { name: /run query/i }));

      await waitFor(() => {
        expect(screen.getByText("Network error")).toBeInTheDocument();
      });
    });
  });

  describe("URL state", () => {
    it("loads query from URL parameter", async () => {
      mockExecuteQuery.mockResolvedValueOnce({
        type: "list",
        results: [],
        total: 0,
        page: 1,
        per_page: 20,
      });

      renderQueryPage("/query?q=tss%20%3E%20100");

      const textarea = screen.getByPlaceholderText(/enter query/i) as HTMLTextAreaElement;
      expect(textarea.value).toBe("tss > 100");

      await waitFor(() => {
        expect(mockExecuteQuery).toHaveBeenCalledWith("tss > 100", 1, 20);
      });
    });
  });
});
