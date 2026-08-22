import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { GearPage } from "./GearPage";
import * as bikesApi from "@/api/bikes";
import type { Bike } from "@/api/types";

vi.mock("@/api/bikes");

const mockFetchBikes = vi.mocked(bikesApi.fetchBikes);
const mockCreateBike = vi.mocked(bikesApi.createBike);
const mockSetDefaultBike = vi.mocked(bikesApi.setDefaultBike);
const mockRetireBike = vi.mocked(bikesApi.retireBike);

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
  estimated_cda_avg: null,
  estimated_crr_avg: null,
  estimated_cda_stddev: null,
  estimated_crr_stddev: null,
  aero_sample_count: null,
};

const mockRetiredBike: Bike = {
  ...mockBike,
  id: 2,
  name: "Old Bike",
  is_default: false,
  retired_at: "2024-06-01T00:00:00Z",
  estimated_cda_avg: null,
  estimated_crr_avg: null,
  estimated_cda_stddev: null,
  estimated_crr_stddev: null,
  aero_sample_count: null,
};

function renderGearPage() {
  return render(
    <MemoryRouter>
      <GearPage unitSystem="metric" />
    </MemoryRouter>
  );
}

describe("GearPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockFetchBikes.mockImplementation(() => new Promise(() => {})); // Never resolves
    renderGearPage();
    
    // Should show loading skeletons
    expect(screen.getByText("Gear")).toBeInTheDocument();
  });

  it("renders empty state when no bikes", async () => {
    mockFetchBikes.mockResolvedValue([]);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("No bikes yet")).toBeInTheDocument();
    });
    expect(screen.getByText("Add your first bike to track distance and performance.")).toBeInTheDocument();
  });

  it("renders bike cards when bikes exist", async () => {
    mockFetchBikes.mockResolvedValue([mockBike]);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("Canyon Aeroad")).toBeInTheDocument();
    });
    // formatDistance returns "5000.0 km" for 5000000m
    expect(screen.getByText("5000.0 km")).toBeInTheDocument();
  });

  it("shows default star indicator for default bike", async () => {
    mockFetchBikes.mockResolvedValue([mockBike]);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByTitle("Default bike")).toBeInTheDocument();
    });
  });

  it("shows retired bikes in collapsible section", async () => {
    mockFetchBikes.mockResolvedValue([mockBike, mockRetiredBike]);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("Retired (1)")).toBeInTheDocument();
    });

    // Retired bike should not be visible initially
    expect(screen.queryByText("Old Bike")).not.toBeInTheDocument();

    // Click to expand
    await userEvent.click(screen.getByText("Retired (1)"));

    // Now retired bike should be visible
    expect(screen.getByText("Old Bike")).toBeInTheDocument();
  });

  it("opens add bike form when clicking Add Bike", async () => {
    mockFetchBikes.mockResolvedValue([]);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("No bikes yet")).toBeInTheDocument();
    });

    // There are two "Add Bike" buttons in empty state - click the first one
    const addButtons = screen.getAllByRole("button", { name: "Add Bike" });
    await userEvent.click(addButtons[0]);

    expect(screen.getByRole("heading", { name: "Add Bike" })).toBeInTheDocument();
  });

  it("opens edit form when clicking Edit on a bike", async () => {
    mockFetchBikes.mockResolvedValue([mockBike]);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("Canyon Aeroad")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(screen.getByRole("heading", { name: "Edit Bike" })).toBeInTheDocument();
    expect(screen.getByDisplayValue("Canyon Aeroad")).toBeInTheDocument();
  });

  it("calls setDefaultBike when clicking Set Default", async () => {
    const nonDefaultBike = { ...mockBike, is_default: false };
    mockFetchBikes.mockResolvedValue([nonDefaultBike]);
    mockSetDefaultBike.mockResolvedValue({ ...nonDefaultBike, is_default: true });
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("Canyon Aeroad")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Set Default" }));

    expect(mockSetDefaultBike).toHaveBeenCalledWith(1);
  });

  it("shows retire confirmation dialog", async () => {
    mockFetchBikes.mockResolvedValue([mockBike]);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("Canyon Aeroad")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Retire" }));

    expect(screen.getByText("Retire Canyon Aeroad?")).toBeInTheDocument();
  });

  it("calls retireBike when confirming retire", async () => {
    mockFetchBikes.mockResolvedValue([mockBike]);
    mockRetireBike.mockResolvedValue({ ...mockBike, retired_at: "2024-06-01T00:00:00Z" });
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("Canyon Aeroad")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Retire" }));
    await userEvent.click(screen.getByRole("button", { name: "Retire" })); // Confirm button

    expect(mockRetireBike).toHaveBeenCalledWith(1);
  });

  it("displays error state when fetch fails", async () => {
    mockFetchBikes.mockRejectedValue(new Error("Network error"));
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("retries fetch when clicking Retry", async () => {
    mockFetchBikes.mockRejectedValueOnce(new Error("Network error"));
    mockFetchBikes.mockResolvedValueOnce([mockBike]);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(screen.getByText("Canyon Aeroad")).toBeInTheDocument();
    });
  });

  it("creates bike via form", async () => {
    mockFetchBikes.mockResolvedValue([]);
    mockCreateBike.mockResolvedValue(mockBike);
    renderGearPage();

    await waitFor(() => {
      expect(screen.getByText("No bikes yet")).toBeInTheDocument();
    });

    // Open form - use first Add Bike button
    const addButtons = screen.getAllByRole("button", { name: "Add Bike" });
    await userEvent.click(addButtons[0]);

    // Fill form
    await userEvent.type(screen.getByLabelText("Name"), "New Bike");
    
    // Submit
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockCreateBike).toHaveBeenCalledWith(expect.objectContaining({
        name: "New Bike",
        bike_type: "road",
      }));
    });
  });
});
