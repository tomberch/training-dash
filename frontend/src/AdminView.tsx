import { useState, useEffect } from "react";
import type { AdminUser } from "./api";
import { fetchAdminUsers, createUser, resetUserPassword, triggerUserSync } from "./api";

export function AdminView({ onBack }: { onBack: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Create user form
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [creating, setCreating] = useState(false);

  // Reset password state
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [resetPassword, setResetPassword] = useState("");

  useEffect(() => {
    loadUsers();
  }, []);

  async function loadUsers() {
    try {
      const data = await fetchAdminUsers();
      setUsers(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    if (!newUsername || !newPassword) return;
    setCreating(true);
    try {
      await createUser(newUsername, newPassword);
      setNewUsername("");
      setNewPassword("");
      await loadUsers();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCreating(false);
    }
  }

  async function handleResetPassword(userId: number) {
    if (!resetPassword) return;
    try {
      await resetUserPassword(userId, resetPassword);
      setResetUserId(null);
      setResetPassword("");
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleTriggerSync(userId: number) {
    try {
      await triggerUserSync(userId);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (loading) return <p>Loading...</p>;

  return (
    <div style={{ padding: "1rem" }}>
      <button onClick={onBack}>Back</button>
      <h1>Admin</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <section style={{ marginBottom: "2rem" }}>
        <h2>Create User</h2>
        <form onSubmit={handleCreateUser} style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            placeholder="Username"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            data-testid="new-username"
          />
          <input
            type="password"
            placeholder="Password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            data-testid="new-password"
          />
          <button type="submit" disabled={creating} data-testid="create-user-btn">
            {creating ? "Creating..." : "Create"}
          </button>
        </form>
      </section>

      <section>
        <h2>Users</h2>
        {users.length === 0 ? (
          <p>No users.</p>
        ) : (
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>ID</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>Username</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>Admin</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>Created</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} data-testid={`user-row-${user.id}`}>
                  <td>{user.id}</td>
                  <td>{user.username}</td>
                  <td>{user.is_admin ? "Yes" : "No"}</td>
                  <td>{new Date(user.created_at).toLocaleDateString()}</td>
                  <td style={{ display: "flex", gap: "0.5rem" }}>
                    {resetUserId === user.id ? (
                      <>
                        <input
                          type="password"
                          placeholder="New password"
                          value={resetPassword}
                          onChange={(e) => setResetPassword(e.target.value)}
                          data-testid={`reset-password-input-${user.id}`}
                        />
                        <button
                          onClick={() => handleResetPassword(user.id)}
                          data-testid={`confirm-reset-btn-${user.id}`}
                        >
                          Save
                        </button>
                        <button onClick={() => setResetUserId(null)}>Cancel</button>
                      </>
                    ) : (
                      <button
                        onClick={() => setResetUserId(user.id)}
                        data-testid={`reset-btn-${user.id}`}
                      >
                        Reset Password
                      </button>
                    )}
                    <button
                      onClick={() => handleTriggerSync(user.id)}
                      data-testid={`sync-btn-${user.id}`}
                    >
                      Trigger Sync
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
