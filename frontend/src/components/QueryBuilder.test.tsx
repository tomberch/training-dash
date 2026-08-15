import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryBuilder } from "./QueryBuilder";

describe("QueryBuilder", () => {
  describe("rendering", () => {
    it("renders field selector", () => {
      render(<QueryBuilder onQueryChange={vi.fn()} />);
      expect(screen.getByText("Select field...")).toBeInTheDocument();
    });

    it("renders add condition button", () => {
      render(<QueryBuilder onQueryChange={vi.fn()} />);
      expect(screen.getByRole("button", { name: /add condition/i })).toBeInTheDocument();
    });

    it("renders field groups in dropdown", () => {
      render(<QueryBuilder onQueryChange={vi.fn()} />);
      // Check for optgroups in the field selector
      expect(screen.getByRole("group", { name: "Time & Date" })).toBeInTheDocument();
      expect(screen.getByRole("group", { name: "Distance & Speed" })).toBeInTheDocument();
      expect(screen.getByRole("group", { name: "Power" })).toBeInTheDocument();
    });
  });

  describe("field selection", () => {
    it("updates operator options when field type changes", async () => {
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={vi.fn()} />);

      const fieldSelect = screen.getAllByRole("combobox")[0];

      // Select a number field (tss)
      await user.selectOptions(fieldSelect, "tss");
      
      // Should have numeric operators
      const operatorSelect = screen.getAllByRole("combobox")[1];
      expect(operatorSelect).toHaveValue(">");
    });

    it("shows date presets for date fields", async () => {
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={vi.fn()} />);

      const fieldSelect = screen.getAllByRole("combobox")[0];
      await user.selectOptions(fieldSelect, "started_at");

      // Date field should show preset dropdown
      expect(screen.getByText("Select date...")).toBeInTheDocument();
      expect(screen.getByRole("option", { name: "Today" })).toBeInTheDocument();
      expect(screen.getByRole("option", { name: "This month" })).toBeInTheDocument();
    });

    it("shows yes/no for boolean fields", async () => {
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={vi.fn()} />);

      const fieldSelect = screen.getAllByRole("combobox")[0];
      await user.selectOptions(fieldSelect, "is_breakthrough");

      // Boolean field should show yes/no
      expect(screen.getByRole("option", { name: "Yes" })).toBeInTheDocument();
      expect(screen.getByRole("option", { name: "No" })).toBeInTheDocument();
    });
  });

  describe("query generation", () => {
    it("generates simple comparison query", async () => {
      const onQueryChange = vi.fn();
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={onQueryChange} />);

      const fieldSelect = screen.getAllByRole("combobox")[0];
      await user.selectOptions(fieldSelect, "tss");

      const valueInput = screen.getByPlaceholderText("Enter value...");
      await user.type(valueInput, "100");

      // Should generate query
      expect(onQueryChange).toHaveBeenLastCalledWith("tss > 100");
    });

    it("generates date query with preset", async () => {
      const onQueryChange = vi.fn();
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={onQueryChange} />);

      // Select date field
      const allSelects = screen.getAllByRole("combobox");
      await user.selectOptions(allSelects[0], "started_at");

      // Find the date preset select (should have START_OF_MONTH option)
      const updatedSelects = screen.getAllByRole("combobox");
      const dateSelect = updatedSelects.find(
        (el) => el.querySelector('option[value="START_OF_MONTH"]')
      );
      expect(dateSelect).toBeTruthy();
      await user.selectOptions(dateSelect!, "START_OF_MONTH");

      expect(onQueryChange).toHaveBeenLastCalledWith("started_at >= START_OF_MONTH");
    });

    it("generates boolean query", async () => {
      const onQueryChange = vi.fn();
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={onQueryChange} />);

      const allSelects = screen.getAllByRole("combobox");
      await user.selectOptions(allSelects[0], "is_breakthrough");

      // Boolean defaults to true, and we should see the query immediately
      // Wait for the callback to be called
      await vi.waitFor(() => {
        expect(onQueryChange).toHaveBeenLastCalledWith("is_breakthrough = true");
      });
    });

    it("generates string query with quotes", async () => {
      const onQueryChange = vi.fn();
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={onQueryChange} />);

      const fieldSelect = screen.getAllByRole("combobox")[0];
      await user.selectOptions(fieldSelect, "title");

      const valueInput = screen.getByPlaceholderText("Enter value...");
      await user.type(valueInput, "Morning Ride");

      expect(onQueryChange).toHaveBeenLastCalledWith('title = "Morning Ride"');
    });
  });

  describe("multiple conditions", () => {
    it("adds new condition when clicking add button", async () => {
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={vi.fn()} />);

      const addButton = screen.getByRole("button", { name: /add condition/i });
      await user.click(addButton);

      // Should have two delete buttons now (one per condition row)
      const deleteButtons = screen.getAllByRole("button", { name: /remove condition/i });
      expect(deleteButtons).toHaveLength(2);
    });

    it("generates AND query with multiple conditions", async () => {
      const onQueryChange = vi.fn();
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={onQueryChange} />);

      // First condition: tss > 100
      const allSelects = screen.getAllByRole("combobox");
      // First select is field, second is operator
      await user.selectOptions(allSelects[0], "tss");
      
      const valueInputs = screen.getAllByRole("textbox");
      await user.type(valueInputs[0], "100");

      // Add second condition
      const addButton = screen.getByRole("button", { name: /add condition/i });
      await user.click(addButton);

      // Get all selects again after adding condition
      const updatedSelects = screen.getAllByRole("combobox");
      // After adding: AND/OR select, field select, operator select, field select, operator select
      // Find the last field select (the new one)
      const fieldSelects = updatedSelects.filter(
        (el) => el.querySelector('option[value="total_distance_m"]')
      );
      await user.selectOptions(fieldSelects[fieldSelects.length - 1], "total_distance_m");
      
      const updatedValueInputs = screen.getAllByRole("textbox");
      await user.type(updatedValueInputs[updatedValueInputs.length - 1], "50000");

      expect(onQueryChange).toHaveBeenLastCalledWith("tss > 100 AND total_distance_m > 50000");
    });

    it("generates OR query when conjunction changed", async () => {
      const onQueryChange = vi.fn();
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={onQueryChange} />);

      // First condition
      const allSelects = screen.getAllByRole("combobox");
      await user.selectOptions(allSelects[0], "tss");
      const valueInputs = screen.getAllByRole("textbox");
      await user.type(valueInputs[0], "100");

      // Add second condition
      const addButton = screen.getByRole("button", { name: /add condition/i });
      await user.click(addButton);

      // Get all selects after adding condition
      const updatedSelects = screen.getAllByRole("combobox");
      
      // Find the AND/OR select (has AND and OR options)
      const andOrSelect = updatedSelects.find(
        (el) => el.querySelector('option[value="AND"]') && el.querySelector('option[value="OR"]')
      );
      expect(andOrSelect).toBeTruthy();
      await user.selectOptions(andOrSelect!, "OR");

      // Second condition - select avg_power_w field
      const fieldSelects = updatedSelects.filter(
        (el) => el.querySelector('option[value="avg_power_w"]')
      );
      await user.selectOptions(fieldSelects[fieldSelects.length - 1], "avg_power_w");
      
      const updatedValueInputs = screen.getAllByRole("textbox");
      await user.type(updatedValueInputs[updatedValueInputs.length - 1], "200");

      expect(onQueryChange).toHaveBeenLastCalledWith("tss > 100 OR avg_power_w > 200");
    });
  });

  describe("removing conditions", () => {
    it("removes condition when clicking delete button", async () => {
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={vi.fn()} />);

      // Add second condition
      const addButton = screen.getByRole("button", { name: /add condition/i });
      await user.click(addButton);

      // Should have 2 delete buttons
      let deleteButtons = screen.getAllByRole("button", { name: /remove condition/i });
      expect(deleteButtons).toHaveLength(2);

      // Remove first condition
      await user.click(deleteButtons[0]);

      // Should have 1 delete button now
      deleteButtons = screen.getAllByRole("button", { name: /remove condition/i });
      expect(deleteButtons).toHaveLength(1);
    });

    it("resets to empty condition when removing last one", async () => {
      const onQueryChange = vi.fn();
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={onQueryChange} />);

      // Set up a condition
      const fieldSelect = screen.getAllByRole("combobox")[0];
      await user.selectOptions(fieldSelect, "tss");
      const valueInput = screen.getByPlaceholderText("Enter value...");
      await user.type(valueInput, "100");

      // Remove the condition
      const deleteButton = screen.getByRole("button", { name: /remove condition/i });
      await user.click(deleteButton);

      // Should reset to empty state
      expect(onQueryChange).toHaveBeenLastCalledWith("");
    });
  });

  describe("clear all", () => {
    it("shows clear all button when query is valid", async () => {
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={vi.fn()} />);

      // Set up a condition
      const fieldSelect = screen.getAllByRole("combobox")[0];
      await user.selectOptions(fieldSelect, "tss");
      const valueInput = screen.getByPlaceholderText("Enter value...");
      await user.type(valueInput, "100");

      expect(screen.getByRole("button", { name: /clear all/i })).toBeInTheDocument();
    });

    it("clears all conditions when clicking clear all", async () => {
      const onQueryChange = vi.fn();
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={onQueryChange} />);

      // Set up a condition
      const fieldSelect = screen.getAllByRole("combobox")[0];
      await user.selectOptions(fieldSelect, "tss");
      const valueInput = screen.getByPlaceholderText("Enter value...");
      await user.type(valueInput, "100");

      // Clear all
      const clearButton = screen.getByRole("button", { name: /clear all/i });
      await user.click(clearButton);

      expect(onQueryChange).toHaveBeenLastCalledWith("");
    });
  });

  describe("query preview", () => {
    it("shows generated query preview", async () => {
      const user = userEvent.setup();
      render(<QueryBuilder onQueryChange={vi.fn()} />);

      const fieldSelect = screen.getAllByRole("combobox")[0];
      await user.selectOptions(fieldSelect, "tss");
      const valueInput = screen.getByPlaceholderText("Enter value...");
      await user.type(valueInput, "100");

      expect(screen.getByText("Generated query:")).toBeInTheDocument();
      expect(screen.getByText("tss > 100")).toBeInTheDocument();
    });
  });
});
