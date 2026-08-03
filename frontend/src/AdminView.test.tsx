import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AdminView } from "./AdminView";

vi.mock("./api", () => ({
  fetchAdminUsers: vi.fn(),
  fetchPendingUsers: vi.fn(),
  fetchAdminSettings: vi.fn(),
  createUser: vi.fn(),
  approveUser: vi.fn(),
  rejectUser: vi.fn(),
  resetUserPassword: vi.fn(),
  triggerUserSync: vi.fn(),
  updateAdminSetting: vi.fn(),
}));

import { 
  fetchAdminUsers, 
  fetchPendingUsers,
  fetchAdminSettings,
  createUser, 
  resetUserPassword, 
  triggerUserSync 
} from "./api";

const mockFetchAdminUsers = vi.mocked(fetchAdminUsers);
const mockFetchPendingUsers = vi.mocked(fetchPendingUsers);
const mockFetchAdminSettings = vi.mocked(fetchAdminSettings);
const mockCreateUser = vi.mocked(createUser);
vi.mocked(resetUserPassword);
const mockTriggerUserSync = vi.mocked(triggerUserSync);

const mockUsers = [
  { id: 1, email: "admin@example.com", display_name: null, is_admin: true, is_approved: true, created_at: "2024-01-01T00:00:00" },
  { id: 2, email: "user1@example.com", display_name: "User One", is_admin: false, is_approved: true, created_at: "2024-02-15T00:00:00" },
];

const mockSettings = { require_approval: true };

describe("AdminView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchPendingUsers.mockResolvedValue([]);
    mockFetchAdminSettings.mockResolvedValue(mockSettings);
  });

  it("renders user list for admin", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      expect(screen.getByText("User One")).toBeInTheDocument();
    });

    // Check status badges
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getAllByText("Approved")).toHaveLength(2);
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
      email: "newuser@example.com",
      display_name: null,
      is_admin: false,
      is_approved: false,
      created_at: "2024-03-01T00:00:00",
    });

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId("create-user-btn")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("new-username"), { target: { value: "newuser@example.com" } });
    fireEvent.change(screen.getByTestId("new-password"), { target: { value: "newpass" } });
    fireEvent.click(screen.getByTestId("create-user-btn"));

    await waitFor(() => {
      expect(mockCreateUser).toHaveBeenCalledWith("newuser@example.com", "newpass");
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
      expect(screen.getByText(/Back/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Back/));
    expect(onBack).toHaveBeenCalled();
  });

  it("shows pending users section when there are pending users", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);
    mockFetchPendingUsers.mockResolvedValue([
      { id: 3, email: "pending@example.com", display_name: null, is_admin: false, is_approved: false, created_at: "2024-03-01T00:00:00" },
    ]);

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("Pending Approval (1)")).toBeInTheDocument();
      expect(screen.getByText("pending@example.com")).toBeInTheDocument();
    });
  });

  it("shows registration settings toggle", async () => {
    mockFetchAdminUsers.mockResolvedValue(mockUsers);

    render(<AdminView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("Registration Settings")).toBeInTheDocument();
      expect(screen.getByText("Require approval for new users")).toBeInTheDocument();
    });
  });
});
