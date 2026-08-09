import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import App from "./App";

// Mock all child components and API
vi.mock("./ActivityList", () => ({
  ActivityList: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <div data-testid="activity-list">
      <button onClick={() => onSelect("test-uuid-1")}>Select Activity</button>
    </div>
  ),
  Login: ({ onLogin }: { onLogin: (isAdmin: boolean) => void }) => (
    <div data-testid="login">
      <button data-testid="login-admin" onClick={() => onLogin(true)}>Login as Admin</button>
      <button data-testid="login-user" onClick={() => onLogin(false)}>Login as User</button>
    </div>
  ),
}));

vi.mock("./ActivityDetail", () => ({
  ActivityDetail: () => <div data-testid="activity-detail">Activity Detail</div>,
}));

vi.mock("./RecordsView", () => ({
  RecordsView: () => <div data-testid="records-view">Records View</div>,
}));

vi.mock("./AdminView", () => ({
  AdminView: () => <div data-testid="admin-view">Admin View</div>,
}));

vi.mock("./Header", () => ({
  Header: ({ username, onLogout, onSettings }: { username: string; onLogout: () => void; onSettings: () => void }) => (
    <div data-testid="header">
      <span data-testid="username">{username}</span>
      <button data-testid="logout" onClick={onLogout}>Logout</button>
      <button data-testid="settings" onClick={onSettings}>Settings</button>
    </div>
  ),
}));

vi.mock("./Settings", () => ({
  Settings: () => <div data-testid="settings-view">Settings</div>,
}));

vi.mock("./pages/Dashboard", () => ({
  Dashboard: () => <div data-testid="dashboard">Dashboard</div>,
}));

vi.mock("./pages/PMCView", () => ({
  PMCView: () => <div data-testid="pmc-view">PMC View</div>,
}));

vi.mock("./pages/PowerCurveView", () => ({
  PowerCurveView: () => <div data-testid="power-curve-view">Power Curve View</div>,
}));

vi.mock("./Sidebar", async () => {
  const { Link } = await import("react-router-dom");
  return {
    Sidebar: ({ isAdmin }: { isAdmin: boolean }) => (
      <div data-testid="sidebar">
        {isAdmin && <Link to="/admin" data-testid="admin-link">Admin</Link>}
      </div>
    ),
  };
});

// Mock API
vi.mock("./api", () => ({
  fetchMe: vi.fn(),
  logout: vi.fn().mockResolvedValue(undefined),
  fetchThresholds: vi.fn().mockResolvedValue([]),
  fetchActivities: vi.fn().mockResolvedValue({ activities: [], pagination: { page: 1, per_page: 1, total: 0, total_pages: 0 } }),
  fetchCurrentMetrics: vi.fn().mockResolvedValue({}),
}));

import { fetchMe } from "./api";

const baseUser = {
  date_of_birth: null,
  weight_kg: null,
  height_cm: null,
  gender: null as "male" | "female" | null,
  power_zone_percentages: null,
  hr_zone_percentages: null,
  hr_derived_power_enabled: false,
};

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows login when not logged in", async () => {
    vi.mocked(fetchMe).mockRejectedValue(new Error("Unauthorized"));
    render(<App />);
    
    await waitFor(() => {
      expect(screen.getByTestId("login")).toBeInTheDocument();
    });
  });

  it("shows admin link when logged in as admin", async () => {
    vi.mocked(fetchMe).mockRejectedValueOnce(new Error("Unauthorized"));
    vi.mocked(fetchMe).mockResolvedValueOnce({ ...baseUser, id: 1, email: "admin@test.com", display_name: null, avatar_path: null, is_admin: true, is_approved: true, unit_system: "metric", sync_hour: 3 });
    
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("login")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("login-admin"));

    await waitFor(() => {
      expect(screen.getByTestId("dashboard")).toBeInTheDocument();
    });

    expect(screen.getByTestId("admin-link")).toBeInTheDocument();
  });

  it("does not show admin link when logged in as non-admin", async () => {
    vi.mocked(fetchMe).mockRejectedValueOnce(new Error("Unauthorized"));
    vi.mocked(fetchMe).mockResolvedValueOnce({ ...baseUser, id: 1, email: "user@test.com", display_name: null, avatar_path: null, is_admin: false, is_approved: true, unit_system: "metric", sync_hour: 3 });
    
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("login")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("login-user"));

    await waitFor(() => {
      expect(screen.getByTestId("dashboard")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("admin-link")).not.toBeInTheDocument();
  });

  it("navigates to admin view when admin clicks admin link", async () => {
    vi.mocked(fetchMe).mockRejectedValueOnce(new Error("Unauthorized"));
    vi.mocked(fetchMe).mockResolvedValueOnce({ ...baseUser, id: 1, email: "admin@test.com", display_name: null, avatar_path: null, is_admin: true, is_approved: true, unit_system: "metric", sync_hour: 3 });
    
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("login")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("login-admin"));

    await waitFor(() => {
      expect(screen.getByTestId("admin-link")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("admin-link"));

    await waitFor(() => {
      expect(screen.getByTestId("admin-view")).toBeInTheDocument();
    });
  });
});
