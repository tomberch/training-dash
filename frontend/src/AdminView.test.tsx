import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AdminView } from "./AdminView";

vi.mock("./api", () => ({
  fetchAdminUsers: vi.fn(),
  createUser: vi.fn(),
  resetUserPassword: vi.fn(),
  triggerUserSync: vi.fn(),
}));

import { fetchAdminUsers, createUser, resetUserPassword, triggerUserSync } from "./api";

const mockFetchAdminUsers = vi.mocked(fetchAdminUsers);
const mockCreateUser = vi.mocked(createUser);
const _mockResetUserPassword = vi.mocked(resetUserPassword);
const mockTriggerUserSync = vi.mocked(triggerUserSync);

const mockUsers = [
  { id: 1, username: "admin", is_admin: true, created_at: "2024-01-01T00:00:00" },
  { id: 2, username: "user1", is_admin: false, created_at: "2024-02-15T00:00:00" },
];

describe("AdminView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders user list for admin", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("admin")).toBeInTheDocument();
      expect(screen.getByText("user1")).toBeInTheDocument();
    });

    // Check admin column
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
  });

  it("shows create user form", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("Create User")).toBeInTheDocument();
    });

    expect(screen.getByTestId("new-username")).toBeInTheDocument();
    expect(screen.getByTestId("new-password")).toBeInTheDocument();
    expect(screen.getByTestId("create-user-btn")).toBeInTheDocument();
  });

  it("creates user when form is submitted", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);
    mockCreateUser.mockResolvedValue({
      id: 3,
      username: "newuser",
      is_admin: false,
      created_at: "2024-03-01T00:00:00",
    });

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId("create-user-btn")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("new-username"), { target: { value: "newuser" } });
    fireEvent.change(screen.getByTestId("new-password"), { target: { value: "newpass" } });
    fireEvent.click(screen.getByTestId("create-user-btn"));

    await waitFor(() => {
      expect(mockCreateUser).toHaveBeenCalledWith("newuser", "newpass");
    });
  });

  it("shows reset password button for each user", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId("reset-btn-1")).toBeInTheDocument();
      expect(screen.getByTestId("reset-btn-2")).toBeInTheDocument();
    });
  });

  it("shows sync button for each user", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId("sync-btn-1")).toBeInTheDocument();
      expect(screen.getByTestId("sync-btn-2")).toBeInTheDocument();
    });
  });

  it("triggers sync when sync button is clicked", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);
    mockTriggerUserSync.mockResolvedValue({ job_id: "job123" });

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId("sync-btn-2")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("sync-btn-2"));

    await waitFor(() => {
      expect(mockTriggerUserSync).toHaveBeenCalledWith(2);
    });
  });

  it("calls onBack when back button is clicked", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);
    const onBack = vi.fn();

    render(<AdminView onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByText("Back")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Back"));
    expect(onBack).toHaveBeenCalled();
  });
});
