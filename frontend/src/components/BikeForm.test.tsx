import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BikeForm } from "./BikeForm";
import type { Bike } from "@/api/types";

const mockBike: Bike = {
  id: 1,
  name: "Canyon Aeroad",
  bike_type: "road",
  model_year: 2023,
  weight_kg: 7.5,
  photo_path: null,
  total_distance_m: 5000000,
  cda: 0.25,
  crr: 0.004,
  cda_source: "manual",
  crr_source: null,
  calibrated_at: null,
  is_default: true,
  retired_at: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("BikeForm", () => {
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnSave.mockResolvedValue(undefined);
  });

  it("renders Add Bike title when creating", () => {
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    expect(screen.getByRole("heading", { name: "Add Bike" })).toBeInTheDocument();
  });

  it("renders Edit Bike title when editing", () => {
    render(<BikeForm open={true} onClose={mockOnClose} bike={mockBike} onSave={mockOnSave} />);
    expect(screen.getByRole("heading", { name: "Edit Bike" })).toBeInTheDocument();
  });

  it("populates form with bike data when editing", () => {
    render(<BikeForm open={true} onClose={mockOnClose} bike={mockBike} onSave={mockOnSave} />);
    
    expect(screen.getByDisplayValue("Canyon Aeroad")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2023")).toBeInTheDocument();
    expect(screen.getByDisplayValue("7.5")).toBeInTheDocument();
    expect(screen.getByDisplayValue("0.25")).toBeInTheDocument();
    expect(screen.getByDisplayValue("0.004")).toBeInTheDocument();
  });

  it("shows is_default checkbox only when creating", () => {
    const { rerender } = render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    expect(screen.getByLabelText("Set as default bike")).toBeInTheDocument();

    rerender(<BikeForm open={true} onClose={mockOnClose} bike={mockBike} onSave={mockOnSave} />);
    expect(screen.queryByLabelText("Set as default bike")).not.toBeInTheDocument();
  });

  it("validates name is required", async () => {
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    
    expect(screen.getByText("Name is required")).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("validates weight range", async () => {
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    await userEvent.type(screen.getByLabelText("Name"), "Test Bike");
    await userEvent.type(screen.getByLabelText(/Weight/), "100");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    
    expect(screen.getByText("Weight must be between 0 and 50 kg")).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("validates CdA range", async () => {
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    await userEvent.type(screen.getByLabelText("Name"), "Test Bike");
    await userEvent.type(screen.getByLabelText(/CdA/), "2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    
    expect(screen.getByText("CdA must be between 0 and 1")).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("validates Crr range", async () => {
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    await userEvent.type(screen.getByLabelText("Name"), "Test Bike");
    await userEvent.type(screen.getByLabelText(/Crr/), "0.5");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    
    expect(screen.getByText("Crr must be between 0 and 0.1")).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("calls onSave with create data", async () => {
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    await userEvent.type(screen.getByLabelText("Name"), "New Bike");
    await userEvent.selectOptions(screen.getByLabelText("Type"), "gravel");
    await userEvent.type(screen.getByLabelText(/Model Year/), "2024");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith({
        name: "New Bike",
        bike_type: "gravel",
        model_year: 2024,
        weight_kg: null,
        cda: null,
        crr: null,
        is_default: false,
      });
    });
  });

  it("calls onSave with update data", async () => {
    render(<BikeForm open={true} onClose={mockOnClose} bike={mockBike} onSave={mockOnSave} />);
    
    const nameInput = screen.getByLabelText("Name");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Updated Name");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith(expect.objectContaining({
        name: "Updated Name",
      }));
    });
  });

  it("calls onClose when clicking Cancel", async () => {
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    
    expect(mockOnClose).toHaveBeenCalled();
  });

  it("shows saving state", async () => {
    mockOnSave.mockImplementation(() => new Promise(() => {})); // Never resolves
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    await userEvent.type(screen.getByLabelText("Name"), "Test Bike");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    
    expect(screen.getByRole("button", { name: "Saving..." })).toBeInTheDocument();
  });

  it("displays error from onSave", async () => {
    mockOnSave.mockRejectedValue(new Error("Server error"));
    render(<BikeForm open={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    await userEvent.type(screen.getByLabelText("Name"), "Test Bike");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });
});
