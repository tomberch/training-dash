import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Settings } from "./Settings";

// Mock all API functions
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    updatePreferences: vi.fn(),
    fetchMyXertCredentials: vi.fn().mockResolvedValue({
      configured: false,
      xert_email: null,
      sync_since: null,
    }),
    saveMyXertCredentials: vi.fn(),
    deleteMyXertCredentials: vi.fn(),
    fetchMyGarminCredentials: vi.fn().mockResolvedValue({
      configured: false,
      garmin_email: null,
      sync_since: null,
    }),
    saveMyGarminCredentials: vi.fn(),
    completeGarminMfa: vi.fn(),
    deleteMyGarminCredentials: vi.fn(),
    fetchThresholds: vi.fn().mockResolvedValue([]),
    createThreshold: vi.fn(),
    fetchCurrentMetrics: vi.fn().mockResolvedValue({}),
    fetchZones: vi.fn().mockResolvedValue({
      power_zones: [],
      hr_zones: [],
    }),
    updateZones: vi.fn(),
    uploadAvatar: vi.fn(),
    deleteAvatar: vi.fn(),
    triggerGarminSync: vi.fn(),
    triggerXertSync: vi.fn(),
  };
});

import {
  updatePreferences,
} from "./api";
import type { User } from "./api";

const mockUser: User = {
  id: 1,
  email: "test@example.com",
  display_name: "Test User",
  avatar_path: null,
  is_admin: false,
  is_approved: true,
  unit_system: "metric",
  sync_hour: 3,
  date_of_birth: null,
  weight_kg: null,
  height_cm: null,
  gender: null,
  power_zone_percentages: null,
  hr_zone_percentages: null,
  hr_derived_power_enabled: false,
  hr_power_model: null,
};

// Helper to wrap Settings with Router context
function renderSettings(props: { user: User; onBack: () => void; onUserUpdate: (user: User) => void }) {
  return render(
    <MemoryRouter>
      <Settings {...props} />
    </MemoryRouter>
  );
}

describe("Settings", () => {
  const mockOnBack = vi.fn();
  const mockOnUserUpdate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders settings page with all sections", async () => {
    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    // Wait for async components to load
    await waitFor(() => {
      expect(screen.getByText("Settings")).toBeInTheDocument();
    });

    expect(screen.getByText("Profile")).toBeInTheDocument();
    expect(screen.getByText("Preferences")).toBeInTheDocument();
    expect(screen.getByText("Training Zones")).toBeInTheDocument();
    expect(screen.getByText("Integrations")).toBeInTheDocument();
  });

  it("calls onBack when back button is clicked", async () => {
    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      expect(screen.getByText("← Back")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("← Back"));
    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  it("displays user email as read-only", async () => {
    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      const emailInput = screen.getByDisplayValue("test@example.com");
      expect(emailInput).toBeDisabled();
    });
  });

  it("displays user display name in input", async () => {
    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test User")).toBeInTheDocument();
    });
  });
});

describe("Settings - Preferences Section", () => {
  const mockOnBack = vi.fn();
  const mockOnUserUpdate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("toggles unit system from metric to imperial", async () => {
    vi.mocked(updatePreferences).mockResolvedValue({
      ...mockUser,
      unit_system: "imperial",
    });

    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      expect(screen.getByTestId("unit-toggle")).toBeInTheDocument();
    });

    const toggle = screen.getByTestId("unit-toggle");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(updatePreferences).toHaveBeenCalledWith({
        unit_system: "imperial",
      });
    });

    expect(mockOnUserUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ unit_system: "imperial" })
    );
  });

  it("shows success feedback after saving preferences", async () => {
    vi.mocked(updatePreferences).mockResolvedValue({
      ...mockUser,
      unit_system: "imperial",
    });

    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      expect(screen.getByTestId("unit-toggle")).toBeInTheDocument();
    });

    const toggle = screen.getByTestId("unit-toggle");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(screen.getByText("Preferences saved")).toBeInTheDocument();
    });
  });

  it("shows error feedback when preferences update fails", async () => {
    vi.mocked(updatePreferences).mockRejectedValue(new Error("Network error"));

    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      expect(screen.getByTestId("unit-toggle")).toBeInTheDocument();
    });

    const toggle = screen.getByTestId("unit-toggle");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(screen.getByText("Failed to save preferences")).toBeInTheDocument();
    });
  });
});

describe("Settings - Profile Section", () => {
  const mockOnBack = vi.fn();
  const mockOnUserUpdate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("saves display name on Save Profile click", async () => {
    vi.mocked(updatePreferences).mockResolvedValue({
      ...mockUser,
      display_name: "New Name",
    });

    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test User")).toBeInTheDocument();
    });

    const displayNameInput = screen.getByDisplayValue("Test User");
    fireEvent.change(displayNameInput, { target: { value: "New Name" } });

    fireEvent.click(screen.getByText("Save Profile"));

    await waitFor(() => {
      expect(updatePreferences).toHaveBeenCalledWith(
        expect.objectContaining({ display_name: "New Name" })
      );
    });

    expect(mockOnUserUpdate).toHaveBeenCalled();
  });

  it("shows success feedback after saving profile", async () => {
    vi.mocked(updatePreferences).mockResolvedValue(mockUser);

    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      expect(screen.getByText("Save Profile")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Save Profile"));

    await waitFor(() => {
      expect(screen.getByText("Profile saved")).toBeInTheDocument();
    });
  });

  it("shows initials when no avatar is set", async () => {
    renderSettings({
      user: mockUser,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      // Display name "Test User" should show "TU" initials
      expect(screen.getByText("TU")).toBeInTheDocument();
    });
  });

  it("shows avatar image when avatar_path is set", async () => {
    const userWithAvatar = {
      ...mockUser,
      avatar_path: "/uploads/avatar.jpg",
    };

    renderSettings({
      user: userWithAvatar,
      onBack: mockOnBack,
      onUserUpdate: mockOnUserUpdate,
    });

    await waitFor(() => {
      const avatarImg = screen.getByAltText("Avatar");
      expect(avatarImg).toHaveAttribute("src", "/uploads/avatar.jpg");
    });
  });
});
