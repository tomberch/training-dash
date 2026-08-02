import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import App from "./App";

// Mock all child components and API
vi.mock("./ActivityList", () => ({
  ActivityList: ({ onSelect }: { onSelect: (id: number) => void }) => (
    <div data-testid="activity-list">
      <button onClick={() => onSelect(1)}>Select Activity</button>
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

// Mock API
vi.mock("./api", () => ({
  fetchMe: vi.fn(),
}));

import { fetchMe } from "./api";

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
    vi.mocked(fetchMe).mockResolvedValueOnce({ id: 1, username: "admin", is_admin: true, unit_system: "metric" });
    
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("login")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("login-admin"));

    await waitFor(() => {
      expect(screen.getByTestId("activity-list")).toBeInTheDocument();
    });

    expect(screen.getByTestId("admin-link")).toBeInTheDocument();
  });

  it("does not show admin link when logged in as non-admin", async () => {
    vi.mocked(fetchMe).mockRejectedValueOnce(new Error("Unauthorized"));
    vi.mocked(fetchMe).mockResolvedValueOnce({ id: 1, username: "user", is_admin: false, unit_system: "metric" });
    
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("login")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("login-user"));

    await waitFor(() => {
      expect(screen.getByTestId("activity-list")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("admin-link")).not.toBeInTheDocument();
  });

  it("navigates to admin view when admin clicks admin link", async () => {
    vi.mocked(fetchMe).mockRejectedValueOnce(new Error("Unauthorized"));
    vi.mocked(fetchMe).mockResolvedValueOnce({ id: 1, username: "admin", is_admin: true, unit_system: "metric" });
    
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
