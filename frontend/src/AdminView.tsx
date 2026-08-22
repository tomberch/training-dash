import { useState, useEffect } from "react";
import type { AdminUser, AdminSettings, NukePreview } from "./api";
import { 
  ApiError, 
  fetchAdminUsers, 
  fetchPendingUsers,
  createUser, 
  approveUser,
  rejectUser,
  resetUserPassword, 
  triggerUserSync,
  fetchAdminSettings,
  updateAdminSetting,
  fetchNukePreview,
  nukeActivities,
  nukeIntegrations,
  nukeAccount,
} from "./api";
import { ErrorDisplay } from "./ErrorDisplay";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

interface SyncStatus {
  userId: number;
  status: "syncing" | "success" | "error";
  message?: string;
}

export function AdminView({ onBack, onSystemDashboard, onBackupSettings }: { onBack: () => void; onSystemDashboard?: () => void; onBackupSettings?: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [pendingUsers, setPendingUsers] = useState<AdminUser[]>([]);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  // Create user form
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [creating, setCreating] = useState(false);

  // Reset password state
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [resetPassword, setResetPassword] = useState("");

  // Sync status per user
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);

  // Approval loading state
  const [approvingUserId, setApprovingUserId] = useState<number | null>(null);

  // Nuke modal state
  const [nukeUser, setNukeUser] = useState<AdminUser | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [usersData, pendingData, settingsData] = await Promise.all([
        fetchAdminUsers(),
        fetchPendingUsers(),
        fetchAdminSettings(),
      ]);
      setUsers(usersData);
      setPendingUsers(pendingData);
      setSettings(settingsData);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    if (!newEmail || !newPassword) return;
    setCreating(true);
    try {
      await createUser(newEmail, newPassword);
      setNewEmail("");
      setNewPassword("");
      await loadData();
    } catch (e) {
      setError(e as Error);
    } finally {
      setCreating(false);
    }
  }

  async function handleApproveUser(userId: number) {
    setApprovingUserId(userId);
    try {
      await approveUser(userId);
      await loadData();
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setApprovingUserId(null);
    }
  }

  async function handleRejectUser(userId: number) {
    if (!confirm("Are you sure you want to reject and delete this user?")) return;
    setApprovingUserId(userId);
    try {
      await rejectUser(userId);
      await loadData();
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setApprovingUserId(null);
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
      setError(e as Error);
    }
  }

  async function handleTriggerSync(userId: number) {
    setSyncStatus({ userId, status: "syncing" });
    try {
      const result = await triggerUserSync(userId);
      if (result.job_id) {
        setSyncStatus({ userId, status: "success", message: `Sync started (job: ${result.job_id.slice(0, 8)}...)` });
      } else {
        setSyncStatus({ userId, status: "success", message: "Sync triggered (no job queue)" });
      }
      setTimeout(() => setSyncStatus(null), 5000);
      setError(null);
    } catch (e) {
      setSyncStatus({ userId, status: "error", message: (e as Error).message });
      setTimeout(() => setSyncStatus(null), 5000);
    }
  }

  async function handleToggleRequireApproval() {
    if (!settings) return;
    const newValue = !settings.require_approval;
    try {
      await updateAdminSetting("require_approval", newValue);
      setSettings({ ...settings, require_approval: newValue });
      setError(null);
    } catch (e) {
      setError(e as Error);
    }
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="space-y-6">
          {/* Header skeleton */}
          <div className="flex items-center gap-4 mb-6">
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-8 w-32" />
          </div>
          
          {/* Pending approvals skeleton */}
          <div className="bg-card rounded-lg border border-border p-6">
            <Skeleton className="h-6 w-40 mb-4" />
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="flex items-center justify-between p-4 border border-border rounded-lg">
                  <div className="flex items-center gap-3">
                    <Skeleton className="w-10 h-10 rounded-full" />
                    <div>
                      <Skeleton className="h-4 w-32 mb-1" />
                      <Skeleton className="h-3 w-48" />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Skeleton className="h-8 w-20" />
                    <Skeleton className="h-8 w-20" />
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Users list skeleton */}
          <div className="bg-card rounded-lg border border-border p-6">
            <Skeleton className="h-6 w-24 mb-4" />
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-center justify-between p-4 border border-border rounded-lg">
                  <div className="flex items-center gap-3">
                    <Skeleton className="w-10 h-10 rounded-full" />
                    <div>
                      <Skeleton className="h-4 w-40 mb-1" />
                      <Skeleton className="h-3 w-56" />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Skeleton className="h-8 w-24" />
                    <Skeleton className="h-8 w-16" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-fast"
            >
              &larr; Back
            </button>
            <h1 className="text-metric">
              Admin Panel
            </h1>
          </div>
          {onSystemDashboard && (
            <button
              onClick={onSystemDashboard}
              className="px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-fast"
            >
              System Dashboard &rarr;
            </button>
          )}
          {onBackupSettings && (
            <button
              onClick={onBackupSettings}
              className="px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-fast"
            >
              Backup Settings &rarr;
            </button>
          )}
        </div>

        {/* Error alert */}
        {error && (
          <div className="mb-6">
            <ErrorDisplay error={error} />
          </div>
        )}

        {/* Settings Section */}
        <section className="mb-8 p-6 bg-card rounded-lg border border-border">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Registration Settings
          </h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Require approval for new users</p>
              <p className="text-body-secondary">
                When enabled, new users must be approved by an admin before they can access the app
              </p>
            </div>
            <button
              onClick={handleToggleRequireApproval}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                settings?.require_approval
                  ? "bg-primary"
                  : "bg-muted"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  settings?.require_approval ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </section>

        {/* Pending Users Section */}
        {pendingUsers.length > 0 && (
          <section className="mb-8 p-6 bg-warning/10 rounded-lg border border-warning/30">
            <h2 className="text-lg font-semibold text-warning mb-4">
              Pending Approval ({pendingUsers.length})
            </h2>
            <div className="space-y-3">
              {pendingUsers.map((user) => (
                <div
                  key={user.id}
                  className="flex items-center justify-between p-3 bg-card rounded-lg border border-warning/30"
                >
                  <div>
                    <p className="font-medium text-foreground">{user.email}</p>
                    <p className="text-caption">
                      Registered {new Date(user.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleApproveUser(user.id)}
                      disabled={approvingUserId === user.id}
                      className="px-3 py-1.5 text-sm font-medium text-primary-foreground bg-success hover:bg-success/80 rounded-lg transition-fast disabled:opacity-50"
                    >
                      {approvingUserId === user.id ? "..." : "Approve"}
                    </button>
                    <button
                      onClick={() => handleRejectUser(user.id)}
                      disabled={approvingUserId === user.id}
                      className="px-3 py-1.5 text-sm font-medium text-destructive bg-destructive/10 hover:bg-destructive/20 rounded-lg transition-fast disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Create User Section */}
        <section className="mb-8 p-6 bg-card rounded-lg border border-border">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Create User
          </h2>
          <form onSubmit={handleCreateUser} className="flex flex-col sm:flex-row gap-3">
            <input
              type="email"
              placeholder="Email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              data-testid="new-username"
              className="flex-1 px-3 py-2 border border-input-border rounded-lg bg-input text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <input
              type="password"
              placeholder="Password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              data-testid="new-password"
              className="flex-1 px-3 py-2 border border-input-border rounded-lg bg-input text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="submit"
              disabled={creating}
              data-testid="create-user-btn"
              className="px-6 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/80 disabled:opacity-50 disabled:cursor-not-allowed transition-fast"
            >
              {creating ? "Creating..." : "Create"}
            </button>
          </form>
        </section>

        {/* Users Table Section */}
        <section className="p-6 bg-card rounded-lg border border-border">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Users
          </h2>
          {users.length === 0 ? (
            <EmptyState
              icon={
                <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                </svg>
              }
              title="No users yet"
              description="Create a user above to get started."
              className="py-8"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-3 px-4 text-left text-section-heading">
                      ID
                    </th>
                    <th className="py-3 px-4 text-left text-section-heading">
                      Email
                    </th>
                    <th className="py-3 px-4 text-left text-section-heading">
                      Status
                    </th>
                    <th className="py-3 px-4 text-left text-section-heading">
                      Created
                    </th>
                    <th className="py-3 px-4 text-left text-section-heading">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {users.map((user) => (
                    <tr
                      key={user.id}
                      data-testid={`user-row-${user.id}`}
                      className="hover:bg-muted/50"
                    >
                      <td className="py-3 px-4 text-sm text-foreground tabular-nums">
                        {user.id}
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-sm font-medium text-foreground">
                          {user.display_name || user.email}
                        </div>
                        {user.display_name && (
                          <div className="text-caption">{user.email}</div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-1">
                          {user.is_admin && (
                            <span className="inline-flex px-2 py-0.5 text-xs font-medium bg-purple-500/20 text-purple-600 rounded-full">
                              Admin
                            </span>
                          )}
                          {user.is_approved ? (
                            <span className="inline-flex px-2 py-0.5 text-xs font-medium bg-success/20 text-success rounded-full">
                              Approved
                            </span>
                          ) : (
                            <span className="inline-flex px-2 py-0.5 text-xs font-medium bg-warning/20 text-warning rounded-full">
                              Pending
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-body-secondary">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-2">
                          {resetUserId === user.id ? (
                            <>
                              <input
                                type="password"
                                placeholder="New password"
                                value={resetPassword}
                                onChange={(e) => setResetPassword(e.target.value)}
                                data-testid={`reset-password-input-${user.id}`}
                                className="w-32 px-2 py-1 text-sm border border-input-border rounded bg-input text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                              />
                              <button
                                onClick={() => handleResetPassword(user.id)}
                                data-testid={`confirm-reset-btn-${user.id}`}
                                className="px-3 py-1 text-xs font-medium bg-primary text-primary-foreground rounded hover:bg-primary/80 transition-fast"
                              >
                                Save
                              </button>
                              <button
                                onClick={() => setResetUserId(null)}
                                className="px-3 py-1 text-xs font-medium bg-muted text-foreground rounded hover:bg-muted/80 transition-fast"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() => setResetUserId(user.id)}
                              data-testid={`reset-btn-${user.id}`}
                              className="px-3 py-1 text-xs font-medium bg-muted text-foreground rounded hover:bg-muted/80 transition-fast"
                            >
                              Reset Password
                            </button>
                          )}
                          <button
                            onClick={() => handleTriggerSync(user.id)}
                            disabled={syncStatus?.userId === user.id && syncStatus.status === "syncing"}
                            data-testid={`sync-btn-${user.id}`}
                            className="px-3 py-1 text-xs font-medium bg-warning/20 text-warning rounded hover:bg-warning/30 disabled:opacity-50 disabled:cursor-not-allowed transition-fast"
                          >
                            {syncStatus?.userId === user.id && syncStatus.status === "syncing"
                              ? "Syncing..."
                              : "Trigger Sync"}
                          </button>
                          {syncStatus?.userId === user.id && syncStatus.status === "success" && (
                            <span className="px-2 py-1 text-xs bg-success/20 text-success rounded">
                              {syncStatus.message}
                            </span>
                          )}
                          {syncStatus?.userId === user.id && syncStatus.status === "error" && (
                            <span className="px-2 py-1 text-xs bg-destructive/20 text-destructive rounded">
                              {syncStatus.message}
                            </span>
                          )}
                          <button
                            onClick={() => setNukeUser(user)}
                            data-testid={`nuke-btn-${user.id}`}
                            className="px-3 py-1 text-xs font-medium bg-destructive/20 text-destructive rounded hover:bg-destructive/30 transition-fast"
                          >
                            Nuke
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

      {/* Nuke Modal */}
      {nukeUser && (
        <NukeModal
          user={nukeUser}
          onClose={() => setNukeUser(null)}
          onComplete={() => {
            setNukeUser(null);
            loadData();
          }}
        />
      )}
    </div>
  );
}

type NukeAction = "activities" | "integrations" | "account";

function NukeModal({
  user,
  onClose,
  onComplete,
}: {
  user: AdminUser;
  onClose: () => void;
  onComplete: () => void;
}) {
  const [preview, setPreview] = useState<NukePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState<NukeAction>("activities");
  const [confirmEmail, setConfirmEmail] = useState("");
  const [nuking, setNuking] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    loadPreview();
  }, [user.id]);

  async function loadPreview() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNukePreview(user.id);
      setPreview(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load preview");
    } finally {
      setLoading(false);
    }
  }

  async function handleNuke() {
    if (confirmEmail.toLowerCase() !== user.email.toLowerCase()) {
      setError("Email does not match");
      return;
    }

    setNuking(true);
    setError(null);
    try {
      let res;
      switch (action) {
        case "activities":
          res = await nukeActivities(user.id, confirmEmail);
          break;
        case "integrations":
          res = await nukeIntegrations(user.id, confirmEmail);
          break;
        case "account":
          res = await nukeAccount(user.id, confirmEmail);
          break;
      }
      setResult(res.deleted);
      setTimeout(() => {
        onComplete();
      }, 2000);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Nuke failed");
    } finally {
      setNuking(false);
    }
  }

  function getActionSummary(): string {
    if (!preview) return "";
    switch (action) {
      case "activities": {
        const a = preview.activities;
        const parts = [];
        if (a.activities) parts.push(`${a.activities} activities`);
        if (a.records) parts.push(`${a.records} records`);
        if (a.laps) parts.push(`${a.laps} laps`);
        if (a.peaks) parts.push(`${a.peaks} peaks`);
        if (a.routes) parts.push(`${a.routes} routes`);
        if (a.fitness_history) parts.push(`${a.fitness_history} fitness history entries`);
        if (a.notifications) parts.push(`${a.notifications} notifications`);
        return parts.length ? parts.join(", ") : "No activity data to delete";
      }
      case "integrations": {
        const i = preview.integrations;
        const parts = [];
        if (i.garmin) parts.push("Garmin credentials");
        if (i.xert) parts.push("Xert credentials");
        return parts.length ? parts.join(", ") : "No integrations configured";
      }
      case "account": {
        return `User account and all associated data (${preview.activities.activities} activities)`;
      }
    }
  }

  const isConfirmValid = confirmEmail.toLowerCase() === user.email.toLowerCase();

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-destructive/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-destructive" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                {preview?.is_self ? "Reset My Data" : "Nuke User Data"}
              </h2>
              <p className="text-body-secondary">
                {user.email}
                {preview?.is_self && " (your account)"}
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">Loading preview...</div>
          ) : error && !result ? (
            <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg text-destructive">
              {error}
            </div>
          ) : result ? (
            <div className="p-4 bg-success/10 border border-success/30 rounded-lg text-success">
              <p className="font-medium">Nuke complete!</p>
              <p className="text-sm mt-1">Deleted: {result}</p>
            </div>
          ) : (
            <>
              {/* Action selector */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  What do you want to delete?
                </label>
                <div className="space-y-2">
                  <label className="flex items-start gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-muted/50">
                    <input
                      type="radio"
                      name="action"
                      value="activities"
                      checked={action === "activities"}
                      onChange={() => setAction("activities")}
                      className="mt-1"
                    />
                    <div>
                      <p className="font-medium text-foreground">Reset Activities</p>
                      <p className="text-body-secondary">
                        Delete activities, records, routes, fitness history. Keep account and credentials.
                      </p>
                    </div>
                  </label>
                  <label className="flex items-start gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-muted/50">
                    <input
                      type="radio"
                      name="action"
                      value="integrations"
                      checked={action === "integrations"}
                      onChange={() => setAction("integrations")}
                      className="mt-1"
                    />
                    <div>
                      <p className="font-medium text-foreground">Disconnect Integrations</p>
                      <p className="text-body-secondary">
                        Delete Garmin and Xert credentials only. Keep all activity data.
                      </p>
                    </div>
                  </label>
                  <label className={`flex items-start gap-3 p-3 border rounded-lg ${
                    preview?.is_self 
                      ? "border-border opacity-50 cursor-not-allowed" 
                      : "border-destructive/30 cursor-pointer hover:bg-destructive/10"
                  }`}>
                    <input
                      type="radio"
                      name="action"
                      value="account"
                      checked={action === "account"}
                      onChange={() => setAction("account")}
                      disabled={preview?.is_self}
                      className="mt-1"
                    />
                    <div>
                      <p className={`font-medium ${preview?.is_self ? "text-muted-foreground" : "text-destructive"}`}>Delete User Account</p>
                      <p className={`text-sm ${preview?.is_self ? "text-muted-foreground" : "text-destructive/80"}`}>
                        {preview?.is_self 
                          ? "Cannot delete your own account." 
                          : "Permanently delete the user and all associated data."}
                      </p>
                    </div>
                  </label>
                </div>
              </div>

              {/* Preview */}
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm font-medium text-foreground mb-1">This will delete:</p>
                <p className="text-sm text-foreground">{getActionSummary()}</p>
              </div>

              {/* Confirmation */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Type <span className="font-mono bg-muted px-1 rounded">{user.email}</span> to confirm
                </label>
                <input
                  type="text"
                  value={confirmEmail}
                  onChange={(e) => setConfirmEmail(e.target.value)}
                  placeholder="Enter email to confirm"
                  className="w-full px-3 py-2 border border-input-border rounded-lg bg-input text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-destructive focus:border-transparent"
                />
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-fast"
          >
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              onClick={handleNuke}
              disabled={!isConfirmValid || nuking || loading}
              className="px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive rounded-lg hover:bg-destructive/80 disabled:opacity-50 disabled:cursor-not-allowed transition-fast"
            >
              {nuking ? "Nuking..." : "Nuke"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
