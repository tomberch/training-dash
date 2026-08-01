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

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows login when not logged in", () => {
    render(<App />);
    expect(screen.getByTestId("login")).toBeInTheDocument();
  });

  it("shows admin link when logged in as admin", async () => {
    render(<App />);

    fireEvent.click(screen.getByTestId("login-admin"));

    await waitFor(() => {
      expect(screen.getByTestId("activity-list")).toBeInTheDocument();
    });

    expect(screen.getByTestId("admin-link")).toBeInTheDocument();
  });

  it("does not show admin link when logged in as non-admin", async () => {
    render(<App />);

    fireEvent.click(screen.getByTestId("login-user"));

    await waitFor(() => {
      expect(screen.getByTestId("activity-list")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("admin-link")).not.toBeInTheDocument();
  });

  it("navigates to admin view when admin clicks admin link", async () => {
    render(<App />);

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
