import { useState, useEffect } from "react";
import type { User, XertCredentialsStatus, GarminCredentialsStatus, OAuthLink } from "@/api";
import {
  updatePreferences,
  fetchMyXertCredentials,
  saveMyXertCredentials,
  deleteMyXertCredentials,
  updateXertSyncEnabled,
  fetchMyGarminCredentials,
  saveMyGarminCredentials,
  completeGarminMfa,
  deleteMyGarminCredentials,
  updateGarminSyncEnabled,
  triggerGarminSync,
  triggerXertSync,
  fetchOAuthLinks,
  disconnectOAuthProvider,
  setPassword,
  hasPassword,
  ApiError,
} from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { FeedbackAlert } from "./FeedbackAlert";
import { PasswordInput } from "./PasswordInput";

interface IntegrationsSettingsProps {
  user: User;
  onUserUpdate: (user: User) => void;
}

export function IntegrationsSettings({ user, onUserUpdate }: IntegrationsSettingsProps) {
  return (
    <div className="space-y-6">
      <SyncScheduleSection user={user} onUserUpdate={onUserUpdate} />
      <XertIntegrationCard />
      <GarminIntegrationCard />
      <ConnectedAccountsSection />
    </div>
  );
}

function SyncScheduleSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const [syncHour, setSyncHour] = useState(user.sync_hour);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  async function handleSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ sync_hour: syncHour });
      onUserUpdate(updated);
      setFeedback({ type: "success", message: "Sync schedule updated" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to update sync schedule";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    if (syncHour !== user.sync_hour) {
      handleSave();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncHour]);


  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Sync Schedule
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="max-w-md">
          <Label className="text-muted-foreground">Daily Sync Time</Label>
          <select
            value={syncHour}
            onChange={(e) => setSyncHour(parseInt(e.target.value))}
            disabled={saving}
            className="w-full h-11 px-4 mt-1.5 rounded-lg border border-input bg-muted text-base focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {Array.from({ length: 24 }, (_, i) => (
              <option key={i} value={i}>
                {i.toString().padStart(2, "0")}:00 UTC
              </option>
            ))}
          </select>
          <p className="text-caption mt-1.5">
            Your integrations (Xert, Garmin) will sync automatically at this hour
          </p>
        </div>
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}

function SyncButton({ onSync, label }: { onSync: () => Promise<{ success: boolean; job_id?: string }>; label: string }) {
  const [syncing, setSyncing] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  async function handleSync() {
    setSyncing(true);
    setFeedback(null);
    try {
      const result = await onSync();
      if (result.success) {
        setFeedback({ type: "success", message: "Sync started" });
        setTimeout(() => setFeedback(null), 3000);
      } else {
        setFeedback({ type: "error", message: "Failed to start sync" });
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to start sync";
      setFeedback({ type: "error", message });
      setTimeout(() => setFeedback(null), 5000);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="relative">
      <Button variant="outline" onClick={handleSync} disabled={syncing} className="border-success/50 text-success hover:bg-success/10">
        {syncing ? "Syncing..." : label}
      </Button>
      {feedback && (
        <div
          className={cn(
            "absolute top-full left-0 mt-1 px-2 py-1 text-xs rounded whitespace-nowrap",
            feedback.type === "success"
              ? "bg-success/20 text-success"
              : "bg-destructive/20 text-destructive"
          )}
        >
          {feedback.message}
        </div>
      )}
    </div>
  );
}



function XertIntegrationCard() {
  const [xertStatus, setXertStatus] = useState<XertCredentialsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [syncSince, setSyncSince] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 90);
    return date.toISOString().split("T")[0];
  });
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetchMyXertCredentials()
      .then((status) => {
        setXertStatus(status);
        if (status.configured && status.xert_email) {
          setEmail(status.xert_email);
        }
        if (status.sync_since) {
          setSyncSince(status.sync_since);
        }
      })
      .catch(() => {
        setXertStatus({ configured: false, xert_email: null, sync_since: null, sync_enabled: true });
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleConnect() {
    if (!email || !password) return;
    setSaving(true);
    setFeedback(null);
    try {
      await saveMyXertCredentials(email, password, syncSince);
      setXertStatus({ configured: true, xert_email: email, sync_since: syncSince, sync_enabled: xertStatus?.sync_enabled ?? true });
      setPassword("");
      setFeedback({ type: "success", message: "Xert connected successfully" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setFeedback({ type: "error", message: "Invalid Xert credentials — check your email and password" });
      } else {
        setFeedback({ type: "error", message: "Failed to connect to Xert" });
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnect() {
    setSaving(true);
    setFeedback(null);
    try {
      await deleteMyXertCredentials();
      setXertStatus({ configured: false, xert_email: null, sync_since: null, sync_enabled: true });
      setEmail("");
      setPassword("");
      setFeedback({ type: "success", message: "Xert disconnected" });
      setTimeout(() => setFeedback(null), 3000);
    } catch {
      setFeedback({ type: "error", message: "Failed to disconnect Xert" });
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="flex items-center gap-3 text-card-title">
            <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold text-primary-foreground">X</span>
            </div>
            <h3 className="text-base font-medium">Xert</h3>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[120px] w-full" />
        </CardContent>
      </Card>
    );
  }



  return (
    <Card className="card-hover">
      <CardHeader>
        <div className="flex items-center justify-between w-full">
          <CardTitle className="flex items-center gap-3 text-card-title">
            <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold text-primary-foreground">X</span>
            </div>
            <h3 className="text-base font-medium">Xert</h3>
          </CardTitle>
          <span
            data-testid="xert-status"
            className={cn(
              "px-3 py-1 text-xs rounded-full",
              xertStatus?.configured
                ? "bg-success/20 text-success"
                : "bg-muted text-muted-foreground"
            )}
          >
            {xertStatus?.configured ? "Connected" : "Not configured"}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-muted-foreground text-sm font-medium">Email</Label>
            {xertStatus?.configured ? (
              <Input type="email" value={email} disabled data-testid="xert-email" className="h-11 px-4 text-base md:text-base bg-muted text-muted-foreground" />
            ) : (
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" data-testid="xert-email" className="h-11 px-4 text-base md:text-base bg-muted" />
            )}
          </div>
          
          <div className="space-y-1.5">
            <Label className="text-muted-foreground text-sm font-medium">{xertStatus?.configured ? "Update Password" : "Password"}</Label>
            <PasswordInput value={password} onChange={setPassword} placeholder={xertStatus?.configured ? "Enter new password to update" : "Enter password"} data-testid="xert-password" />
          </div>
          
          {!xertStatus?.configured && (
            <div className="space-y-1.5">
              <Label className="text-muted-foreground text-sm font-medium">Sync activities since</Label>
              <Input type="date" value={syncSince} onChange={(e) => setSyncSince(e.target.value)} data-testid="xert-sync-since" className="h-11 px-4 text-base md:text-base bg-muted" />
              <p className="text-xs text-muted-foreground mt-1.5">Activities from this date onwards will be imported</p>
            </div>
          )}
          
          {xertStatus?.configured ? (
            <>
              {password && (
                <Button onClick={handleConnect} disabled={saving} data-testid="xert-save-password">
                  {saving ? "Saving..." : "Save Password"}
                </Button>
              )}
              
              <div className="flex items-center justify-between py-3 border-t border-border">
                <div>
                  <p className="font-medium text-sm">Auto-sync from Xert</p>
                  <p className="text-xs text-muted-foreground">Automatically import new activities at your daily sync time</p>
                </div>
                <button
                  onClick={async () => {
                    try {
                      const newValue = !xertStatus.sync_enabled;
                      await updateXertSyncEnabled(newValue);
                      setXertStatus({ ...xertStatus, sync_enabled: newValue });
                    } catch {
                      setFeedback({ type: "error", message: "Failed to update sync setting" });
                    }
                  }}
                  disabled={saving}
                  aria-pressed={xertStatus.sync_enabled}
                  className={cn(
                    "relative inline-flex h-6 w-12 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
                    xertStatus.sync_enabled ? "bg-primary" : "bg-muted",
                    saving && "opacity-50 cursor-not-allowed"
                  )}
                >
                  <span className={cn("pointer-events-none absolute left-1 bottom-1 w-4 h-4 transform rounded-full bg-muted-foreground shadow transition duration-200 ease-in-out", xertStatus.sync_enabled ? "translate-x-6 bg-white" : "translate-x-0")} />
                </button>
              </div>
              
              <div className="flex gap-3 pt-2">
                <SyncButton onSync={triggerXertSync} label="Sync Now" />
                <Button variant="destructive" onClick={handleDisconnect} disabled={saving} data-testid="xert-disconnect">Disconnect</Button>
              </div>
            </>
          ) : (
            <Button onClick={handleConnect} disabled={saving || !email || !password} data-testid="xert-connect">
              {saving ? "Connecting..." : "Connect"}
            </Button>
          )}
        </div>
        
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}



function GarminIntegrationCard() {
  const [garminStatus, setGarminStatus] = useState<GarminCredentialsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [syncSince, setSyncSince] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 90);
    return date.toISOString().split("T")[0];
  });
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetchMyGarminCredentials()
      .then((status) => {
        setGarminStatus(status);
        if (status.configured && status.garmin_email) {
          setEmail(status.garmin_email);
        }
        if (status.sync_since) {
          setSyncSince(status.sync_since);
        }
      })
      .catch(() => {
        setGarminStatus({ configured: false, garmin_email: null, sync_since: null, sync_enabled: true });
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleConnect() {
    if (!email || !password) return;
    setSaving(true);
    setFeedback(null);
    try {
      const response = await saveMyGarminCredentials(email, password, syncSince);
      if (response.mfa_required) {
        setMfaRequired(true);
        setFeedback({ type: "success", message: "MFA required — enter the code from your authenticator app or email" });
      } else {
        setGarminStatus({ configured: true, garmin_email: email, sync_since: syncSince, sync_enabled: garminStatus?.sync_enabled ?? true });
        setPassword("");
        setMfaRequired(false);
        setMfaCode("");
        setFeedback({ type: "success", message: "Garmin connected successfully" });
        setTimeout(() => setFeedback(null), 3000);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setFeedback({ type: "error", message: "Invalid Garmin credentials — check your email and password" });
      } else {
        setFeedback({ type: "error", message: "Failed to connect to Garmin" });
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleMfaSubmit() {
    if (!mfaCode) return;
    setSaving(true);
    setFeedback(null);
    try {
      await completeGarminMfa(mfaCode);
      setGarminStatus({ configured: true, garmin_email: email, sync_since: syncSince, sync_enabled: garminStatus?.sync_enabled ?? true });
      setPassword("");
      setMfaRequired(false);
      setMfaCode("");
      setFeedback({ type: "success", message: "Garmin connected successfully" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setFeedback({ type: "error", message: "Invalid MFA code — please try again" });
      } else {
        setFeedback({ type: "error", message: "Failed to complete MFA" });
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnect() {
    setSaving(true);
    setFeedback(null);
    try {
      await deleteMyGarminCredentials();
      setGarminStatus({ configured: false, garmin_email: null, sync_since: null, sync_enabled: true });
      setEmail("");
      setPassword("");
      setMfaRequired(false);
      setMfaCode("");
      setFeedback({ type: "success", message: "Garmin disconnected" });
      setTimeout(() => setFeedback(null), 3000);
    } catch {
      setFeedback({ type: "error", message: "Failed to disconnect Garmin" });
    } finally {
      setSaving(false);
    }
  }

  function handleCancelMfa() {
    setMfaRequired(false);
    setMfaCode("");
    setPassword("");
    setFeedback(null);
  }

  async function handleToggleSync() {
    if (!garminStatus?.configured) return;
    const newValue = !garminStatus.sync_enabled;
    try {
      await updateGarminSyncEnabled(newValue);
      setGarminStatus({ ...garminStatus, sync_enabled: newValue });
    } catch {
      setFeedback({ type: "error", message: "Failed to update sync setting" });
    }
  }

  if (loading) {
    return (
      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="flex items-center gap-3 text-card-title">
            <div className="w-10 h-10 bg-accent rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold text-accent-foreground">G</span>
            </div>
            <h3 className="text-base font-medium">Garmin</h3>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[120px] w-full" />
        </CardContent>
      </Card>
    );
  }



  return (
    <Card className="card-hover">
      <CardHeader>
        <div className="flex items-center justify-between w-full">
          <CardTitle className="flex items-center gap-3 text-card-title">
            <div className="w-10 h-10 bg-accent rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold text-accent-foreground">G</span>
            </div>
            <h3 className="text-base font-medium">Garmin</h3>
          </CardTitle>
          <span
            data-testid="garmin-status"
            className={cn("px-3 py-1 text-xs rounded-full", garminStatus?.configured ? "bg-success/20 text-success" : "bg-muted text-muted-foreground")}
          >
            {garminStatus?.configured ? "Connected" : "Not configured"}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {mfaRequired ? (
          <MfaForm mfaCode={mfaCode} setMfaCode={setMfaCode} saving={saving} onSubmit={handleMfaSubmit} onCancel={handleCancelMfa} />
        ) : (
          <GarminCredentialsForm
            email={email} setEmail={setEmail} password={password} setPassword={setPassword}
            syncSince={syncSince} setSyncSince={setSyncSince} saving={saving}
            configured={garminStatus?.configured ?? false} syncEnabled={garminStatus?.sync_enabled ?? true}
            onConnect={handleConnect} onDisconnect={handleDisconnect} onToggleSync={handleToggleSync}
          />
        )}
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}

function MfaForm({ mfaCode, setMfaCode, saving, onSubmit, onCancel }: {
  mfaCode: string; setMfaCode: (v: string) => void; saving: boolean; onSubmit: () => void; onCancel: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label className="text-muted-foreground">MFA Code</Label>
        <Input type="text" value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} placeholder="Enter 6-digit code" data-testid="garmin-mfa-code" autoComplete="one-time-code" className="h-11 px-4 text-base md:text-base" />
        <p className="text-caption">Enter the code from your Garmin authenticator app or email</p>
      </div>
      <div className="flex gap-3">
        <Button onClick={onSubmit} disabled={saving || !mfaCode} data-testid="garmin-mfa-submit">{saving ? "Verifying..." : "Verify"}</Button>
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
      </div>
    </div>
  );
}

function GarminCredentialsForm({
  email, setEmail, password, setPassword, syncSince, setSyncSince, saving, configured, syncEnabled, onConnect, onDisconnect, onToggleSync
}: {
  email: string; setEmail: (v: string) => void; password: string; setPassword: (v: string) => void;
  syncSince: string; setSyncSince: (v: string) => void; saving: boolean; configured: boolean; syncEnabled: boolean;
  onConnect: () => void; onDisconnect: () => void; onToggleSync: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label className="text-muted-foreground text-sm font-medium">Email</Label>
        {configured ? (
          <Input type="email" value={email} disabled data-testid="garmin-email" className="h-11 px-4 text-base md:text-base bg-muted text-muted-foreground" />
        ) : (
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" data-testid="garmin-email" className="h-11 px-4 text-base md:text-base bg-muted" />
        )}
      </div>
      <div className="space-y-1.5">
        <Label className="text-muted-foreground text-sm font-medium">{configured ? "Update Password" : "Password"}</Label>
        <PasswordInput value={password} onChange={setPassword} placeholder={configured ? "Enter new password to update" : "Enter password"} data-testid="garmin-password" />
      </div>
      {!configured && (
        <div className="space-y-1.5">
          <Label className="text-muted-foreground text-sm font-medium">Sync activities since</Label>
          <Input type="date" value={syncSince} onChange={(e) => setSyncSince(e.target.value)} data-testid="garmin-sync-since" className="h-11 px-4 text-base md:text-base bg-muted" />
          <p className="text-xs text-muted-foreground mt-1.5">Activities from this date onwards will be imported</p>
        </div>
      )}
      {configured ? (
        <>
          {password && <Button onClick={onConnect} disabled={saving} data-testid="garmin-save-password">{saving ? "Saving..." : "Save Password"}</Button>}
          <div className="flex items-center justify-between py-3 border-t border-border">
            <div>
              <p className="font-medium text-sm">Auto-sync from Garmin</p>
              <p className="text-xs text-muted-foreground">Automatically import new activities at your daily sync time</p>
            </div>
            <button onClick={onToggleSync} disabled={saving} aria-pressed={syncEnabled}
              className={cn("relative inline-flex h-6 w-12 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2", syncEnabled ? "bg-primary" : "bg-muted", saving && "opacity-50 cursor-not-allowed")}>
              <span className={cn("pointer-events-none absolute left-1 bottom-1 w-4 h-4 transform rounded-full bg-muted-foreground shadow transition duration-200 ease-in-out", syncEnabled ? "translate-x-6 bg-white" : "translate-x-0")} />
            </button>
          </div>
          <div className="flex gap-3 pt-2">
            <SyncButton onSync={triggerGarminSync} label="Sync Now" />
            <Button variant="destructive" onClick={onDisconnect} disabled={saving} data-testid="garmin-disconnect">Disconnect</Button>
          </div>
        </>
      ) : (
        <Button onClick={onConnect} disabled={saving || !email || !password} data-testid="garmin-connect">{saving ? "Connecting..." : "Connect"}</Button>
      )}
    </div>
  );
}



function ConnectedAccountsSection(): React.JSX.Element {
  const [oauthLinks, setOauthLinks] = useState<OAuthLink[]>([]);
  const [userHasPassword, setUserHasPassword] = useState(true);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [settingPassword, setSettingPassword] = useState(false);

  useEffect(() => {
    Promise.all([fetchOAuthLinks(), hasPassword()])
      .then(([links, pwdStatus]) => {
        setOauthLinks(links);
        setUserHasPassword(pwdStatus.has_password);
      })
      .catch(() => setOauthLinks([]))
      .finally(() => setLoading(false));
  }, []);

  async function handleDisconnect(provider: string) {
    setDisconnecting(provider);
    setFeedback(null);
    try {
      await disconnectOAuthProvider(provider);
      setOauthLinks(oauthLinks.filter((l) => l.provider !== provider));
      setFeedback({ type: "success", message: `Disconnected ${provider}` });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to disconnect";
      setFeedback({ type: "error", message });
    } finally {
      setDisconnecting(null);
    }
  }

  async function handleSetPassword() {
    if (newPassword !== confirmPassword) {
      setFeedback({ type: "error", message: "Passwords do not match" });
      return;
    }
    if (newPassword.length < 8) {
      setFeedback({ type: "error", message: "Password must be at least 8 characters" });
      return;
    }
    setSettingPassword(true);
    setFeedback(null);
    try {
      await setPassword(newPassword);
      setUserHasPassword(true);
      setShowPasswordForm(false);
      setNewPassword("");
      setConfirmPassword("");
      setFeedback({ type: "success", message: "Password set successfully" });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to set password";
      setFeedback({ type: "error", message });
    } finally {
      setSettingPassword(false);
    }
  }

  const googleLink = oauthLinks.find((l) => l.provider === "google");
  const githubLink = oauthLinks.find((l) => l.provider === "github");
  const canDisconnect = userHasPassword || oauthLinks.length > 1;

  if (loading) {
    return (
      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-card-title">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            Login Methods
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
            <div className="flex items-center gap-4">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div><Skeleton className="h-4 w-20 mb-1" /><Skeleton className="h-3 w-32" /></div>
            </div>
            <Skeleton className="h-9 w-24" />
          </div>
          <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
            <div className="flex items-center gap-4">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div><Skeleton className="h-4 w-20 mb-1" /><Skeleton className="h-3 w-32" /></div>
            </div>
            <Skeleton className="h-9 w-24" />
          </div>
        </CardContent>
      </Card>
    );
  }



  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
          Login Methods
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <FeedbackAlert feedback={feedback} />

        {/* Google */}
        <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            </div>
            <div>
              <h3 className="font-medium text-foreground">Google</h3>
              {googleLink ? <p className="text-sm text-muted-foreground">{googleLink.provider_email}</p> : <p className="text-sm text-muted-foreground">Not connected</p>}
            </div>
          </div>
          {googleLink ? (
            <button onClick={() => handleDisconnect("google")} disabled={disconnecting === "google" || !canDisconnect}
              title={!canDisconnect ? "Set a password before disconnecting your last OAuth provider" : undefined}
              className="bg-destructive/10 text-destructive hover:bg-destructive/20 px-4 py-2 rounded-lg transition text-sm font-medium disabled:opacity-50">
              {disconnecting === "google" ? "..." : "Disconnect"}
            </button>
          ) : (
            <a href="/auth/google/connect" className="bg-muted hover:bg-muted/80 border border-border px-4 py-2 rounded-lg transition text-sm font-medium text-foreground">Connect</a>
          )}
        </div>

        {/* GitHub */}
        <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-background rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-foreground" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
            </div>
            <div>
              <h3 className="font-medium text-foreground">GitHub</h3>
              {githubLink ? <p className="text-sm text-muted-foreground">{githubLink.provider_email || githubLink.display_name}</p> : <p className="text-sm text-muted-foreground">Not connected</p>}
            </div>
          </div>
          {githubLink ? (
            <button onClick={() => handleDisconnect("github")} disabled={disconnecting === "github" || !canDisconnect}
              title={!canDisconnect ? "Set a password before disconnecting your last OAuth provider" : undefined}
              className="bg-destructive/10 text-destructive hover:bg-destructive/20 px-4 py-2 rounded-lg transition text-sm font-medium disabled:opacity-50">
              {disconnecting === "github" ? "..." : "Disconnect"}
            </button>
          ) : (
            <a href="/auth/github/connect" className="bg-muted hover:bg-muted/80 border border-border px-4 py-2 rounded-lg transition text-sm font-medium text-foreground">Connect</a>
          )}
        </div>

        {/* Password section for OAuth-only users */}
        {!userHasPassword && (
          <div className="mt-6 pt-6 border-t border-border">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-medium text-foreground">Password</div>
                <div className="text-body-secondary">Set a password to enable email/password login</div>
              </div>
              {!showPasswordForm && <Button variant="outline" size="sm" onClick={() => setShowPasswordForm(true)}>Set Password</Button>}
            </div>
            {showPasswordForm && (
              <div className="mt-4 space-y-3">
                <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password (min 8 characters)" />
                <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirm password" />
                <div className="flex gap-2">
                  <Button onClick={handleSetPassword} disabled={settingPassword}>{settingPassword ? "Saving..." : "Save Password"}</Button>
                  <Button variant="ghost" onClick={() => { setShowPasswordForm(false); setNewPassword(""); setConfirmPassword(""); }}>Cancel</Button>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
