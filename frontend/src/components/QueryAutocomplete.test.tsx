import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryAutocomplete, QueryHelpPanel } from "./QueryAutocomplete";

describe("QueryAutocomplete", () => {
  const defaultProps = {
    value: "",
    onChange: vi.fn(),
    onExecute: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("basic rendering", () => {
    it("renders textarea with placeholder", () => {
      render(<QueryAutocomplete {...defaultProps} placeholder="Test placeholder" />);
      expect(screen.getByPlaceholderText("Test placeholder")).toBeInTheDocument();
    });

    it("renders with initial value", () => {
      render(<QueryAutocomplete {...defaultProps} value="tss > 100" />);
      expect(screen.getByDisplayValue("tss > 100")).toBeInTheDocument();
    });

    it("applies disabled state", () => {
      render(<QueryAutocomplete {...defaultProps} disabled />);
      expect(screen.getByRole("textbox")).toBeDisabled();
    });

    it("applies error styling when hasError is true", () => {
      render(<QueryAutocomplete {...defaultProps} hasError />);
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveClass("border-destructive");
    });
  });

  describe("input handling", () => {
    it("calls onChange when typing", async () => {
      const onChange = vi.fn();
      render(<QueryAutocomplete {...defaultProps} onChange={onChange} />);
      
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "test" } });
      
      expect(onChange).toHaveBeenCalledWith("test");
    });

    it("calls onExecute on Ctrl+Enter", async () => {
      const onExecute = vi.fn();
      render(<QueryAutocomplete {...defaultProps} value="tss > 100" onExecute={onExecute} />);
      
      const textarea = screen.getByRole("textbox");
      fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });
      
      expect(onExecute).toHaveBeenCalled();
    });

    it("calls onExecute on Cmd+Enter (Mac)", async () => {
      const onExecute = vi.fn();
      render(<QueryAutocomplete {...defaultProps} value="tss > 100" onExecute={onExecute} />);
      
      const textarea = screen.getByRole("textbox");
      fireEvent.keyDown(textarea, { key: "Enter", metaKey: true });
      
      expect(onExecute).toHaveBeenCalled();
    });

    it("does not call onExecute when disabled", async () => {
      const onExecute = vi.fn();
      render(<QueryAutocomplete {...defaultProps} value="tss > 100" onExecute={onExecute} disabled />);
      
      const textarea = screen.getByRole("textbox");
      fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });
      
      expect(onExecute).not.toHaveBeenCalled();
    });

    it("does not call onExecute when value is empty", async () => {
      const onExecute = vi.fn();
      render(<QueryAutocomplete {...defaultProps} value="" onExecute={onExecute} />);
      
      const textarea = screen.getByRole("textbox");
      fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });
      
      expect(onExecute).not.toHaveBeenCalled();
    });
  });

  describe("suggestions", () => {
    it("shows field suggestions when typing a field name prefix", async () => {
      const { rerender } = render(<QueryAutocomplete {...defaultProps} value="" />);
      
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      
      // Simulate typing "ts"
      rerender(<QueryAutocomplete {...defaultProps} value="ts" />);
      
      // Set cursor position
      Object.defineProperty(textarea, 'selectionStart', { value: 2, writable: true });
      Object.defineProperty(textarea, 'selectionEnd', { value: 2, writable: true });
      
      fireEvent.focus(textarea);
      
      await waitFor(() => {
        expect(screen.getByText("tss")).toBeInTheDocument();
      });
    });

    it("shows suggestions for common aliases", async () => {
      const { rerender } = render(<QueryAutocomplete {...defaultProps} value="" />);
      
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      
      rerender(<QueryAutocomplete {...defaultProps} value="dis" />);
      
      Object.defineProperty(textarea, 'selectionStart', { value: 3, writable: true });
      Object.defineProperty(textarea, 'selectionEnd', { value: 3, writable: true });
      
      fireEvent.focus(textarea);
      
      await waitFor(() => {
        expect(screen.getByText("distance")).toBeInTheDocument();
      });
    });

    it("applies suggestion on click", async () => {
      const onChange = vi.fn();
      const { rerender } = render(<QueryAutocomplete {...defaultProps} value="" onChange={onChange} />);
      
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      
      rerender(<QueryAutocomplete {...defaultProps} value="ts" onChange={onChange} />);
      
      Object.defineProperty(textarea, 'selectionStart', { value: 2, writable: true });
      Object.defineProperty(textarea, 'selectionEnd', { value: 2, writable: true });
      
      fireEvent.focus(textarea);
      
      await waitFor(() => {
        expect(screen.getByText("tss")).toBeInTheDocument();
      });
      
      fireEvent.click(screen.getByText("tss"));
      
      expect(onChange).toHaveBeenCalledWith("tss");
    });

    it("navigates suggestions with arrow keys", async () => {
      const { rerender } = render(<QueryAutocomplete {...defaultProps} value="" />);
      
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      
      rerender(<QueryAutocomplete {...defaultProps} value="t" />);
      
      Object.defineProperty(textarea, 'selectionStart', { value: 1, writable: true });
      Object.defineProperty(textarea, 'selectionEnd', { value: 1, writable: true });
      
      fireEvent.focus(textarea);
      
      await waitFor(() => {
        // Should have suggestions visible
        const buttons = screen.queryAllByRole("button");
        expect(buttons.length).toBeGreaterThan(0);
      });
      
      // Press down arrow to move selection
      fireEvent.keyDown(textarea, { key: "ArrowDown" });
      fireEvent.keyDown(textarea, { key: "ArrowUp" });
      
      // Verify arrow keys don't trigger onChange
      expect(defaultProps.onChange).not.toHaveBeenCalled();
    });

    it("closes suggestions on Escape", async () => {
      const { rerender } = render(<QueryAutocomplete {...defaultProps} value="" />);
      
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      
      rerender(<QueryAutocomplete {...defaultProps} value="ts" />);
      
      Object.defineProperty(textarea, 'selectionStart', { value: 2, writable: true });
      Object.defineProperty(textarea, 'selectionEnd', { value: 2, writable: true });
      
      fireEvent.focus(textarea);
      
      await waitFor(() => {
        expect(screen.getByText("tss")).toBeInTheDocument();
      });
      
      fireEvent.keyDown(textarea, { key: "Escape" });
      
      await waitFor(() => {
        // Suggestions should be hidden (look for suggestion button absence)
        const buttons = screen.queryAllByRole("button");
        const suggestionButtons = buttons.filter(b => b.textContent?.includes("tss") && b.textContent?.includes("Training Stress"));
        expect(suggestionButtons.length).toBe(0);
      });
    });

    it("shows date value suggestions after date comparisons", async () => {
      const { rerender } = render(<QueryAutocomplete {...defaultProps} value="" />);
      
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      
      rerender(<QueryAutocomplete {...defaultProps} value="date = TO" />);
      
      Object.defineProperty(textarea, 'selectionStart', { value: 10, writable: true });
      Object.defineProperty(textarea, 'selectionEnd', { value: 10, writable: true });
      
      fireEvent.focus(textarea);
      
      await waitFor(() => {
        expect(screen.getByText("TODAY")).toBeInTheDocument();
      });
    });
  });

  describe("accessibility", () => {
    it("has accessible textarea", () => {
      render(<QueryAutocomplete {...defaultProps} placeholder="Search" />);
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("suggestion buttons are clickable", async () => {
      const { rerender } = render(<QueryAutocomplete {...defaultProps} value="" />);
      
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      
      rerender(<QueryAutocomplete {...defaultProps} value="ts" />);
      
      Object.defineProperty(textarea, 'selectionStart', { value: 2, writable: true });
      Object.defineProperty(textarea, 'selectionEnd', { value: 2, writable: true });
      
      fireEvent.focus(textarea);
      
      await waitFor(() => {
        const buttons = screen.getAllByRole("button");
        expect(buttons.length).toBeGreaterThan(0);
      });
    });
  });
});

describe("QueryHelpPanel", () => {
  it("renders collapsed by default", () => {
    render(<QueryHelpPanel />);
    expect(screen.getByText("Query Syntax Help")).toBeInTheDocument();
    expect(screen.queryByText("Basic Syntax")).not.toBeInTheDocument();
  });

  it("expands when clicked", async () => {
    render(<QueryHelpPanel />);
    
    const button = screen.getByText("Query Syntax Help");
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(screen.getByText("Basic Syntax")).toBeInTheDocument();
    });
  });

  it("shows operators section when expanded", async () => {
    render(<QueryHelpPanel />);
    
    fireEvent.click(screen.getByText("Query Syntax Help"));
    
    await waitFor(() => {
      expect(screen.getByText("Operators")).toBeInTheDocument();
    });
  });

  it("shows common fields section when expanded", async () => {
    render(<QueryHelpPanel />);
    
    fireEvent.click(screen.getByText("Query Syntax Help"));
    
    await waitFor(() => {
      expect(screen.getByText("Common Fields")).toBeInTheDocument();
    });
  });

  it("shows date values section when expanded", async () => {
    render(<QueryHelpPanel />);
    
    fireEvent.click(screen.getByText("Query Syntax Help"));
    
    await waitFor(() => {
      expect(screen.getByText("Date Values")).toBeInTheDocument();
    });
  });

  it("shows examples section when expanded", async () => {
    render(<QueryHelpPanel />);
    
    fireEvent.click(screen.getByText("Query Syntax Help"));
    
    await waitFor(() => {
      expect(screen.getByText("Examples")).toBeInTheDocument();
    });
  });

  it("collapses when clicked again", async () => {
    render(<QueryHelpPanel />);
    
    const button = screen.getByText("Query Syntax Help");
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(screen.getByText("Basic Syntax")).toBeInTheDocument();
    });
    
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(screen.queryByText("Basic Syntax")).not.toBeInTheDocument();
    });
  });
});
