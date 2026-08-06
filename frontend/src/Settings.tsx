import { useState, useEffect, useRef } from "react";
import {
  updatePreferences,
  fetchMyXertCredentials,
  saveMyXertCredentials,
  deleteMyXertCredentials,
  fetchMyGarminCredentials,
  saveMyGarminCredentials,
  completeGarminMfa,
  deleteMyGarminCredentials,
  fetchThresholds,
  createThreshold,
  fetchZones,
  updateZones,
  uploadAvatar,
  deleteAvatar,
  triggerGarminSync,
  triggerXertSync,
  fetchOAuthLinks,
  disconnectOAuthProvider,
  setPassword,
  hasPassword,
  ApiError,
} from "./api";
import type { 
  User, 
  XertCredentialsStatus, 
  GarminCredentialsStatus,
  ThresholdEntry,
  PowerZone,
  HrZone,
  OAuthLink,
} from "./api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent, CardAction } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useTheme } from "./hooks/useTheme";
import type { Theme } from "./hooks/useTheme";
import { SunIcon, MoonIcon, MonitorIcon } from "./components/icons/ThemeIcons";

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

function EyeSlashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
    </svg>
  );
}



// Reusable feedback alert component
function FeedbackAlert({ feedback }: { feedback: { type: "success" | "error"; message: string } | null }) {
  if (!feedback) return null;
  return (
    <div
      className={cn(
        "mt-4 p-3 rounded-lg text-sm border",
        feedback.type === "success"
          ? "bg-success/10 text-success border-success/20"
          : "bg-destructive/10 text-destructive border-destructive/20"
      )}
    >
      {feedback.message}
    </div>
  );
}

function PasswordInput({
  value,
  onChange,
  placeholder,
  "data-testid": dataTestId,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  "data-testid"?: string;
}) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="relative">
      <Input
        type={showPassword ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid={dataTestId}
        className="pr-10"
      />
      <button
        type="button"
        onClick={() => setShowPassword(!showPassword)}
        className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground"
        tabIndex={-1}
      >
        {showPassword ? (
          <EyeSlashIcon className="w-5 h-5" />
        ) : (
          <EyeIcon className="w-5 h-5" />
        )}
      </button>
    </div>
  );
}

interface SettingsProps {
  user: User;
  onBack: () => void;
  onUserUpdate: (user: User) => void;
}



export function Settings({ user, onBack, onUserUpdate }: SettingsProps) {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <Button variant="outline" onClick={onBack} className="mb-6">
          &larr; Back
        </Button>
        
        <h1 className="text-2xl font-bold text-foreground mb-6">Settings</h1>
        
        <div className="space-y-6">
          <ProfileSection user={user} onUserUpdate={onUserUpdate} />
          <PreferencesSection user={user} onUserUpdate={onUserUpdate} />
          <ConnectedAccountsSection />
          <ThresholdsSection />
          <ZonesSection />
          <IntegrationsSection />
        </div>
      </div>
    </div>
  );
}

function ProfileSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const [displayName, setDisplayName] = useState(user.display_name || "");
  const [syncHour, setSyncHour] = useState(user.sync_hour);
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleSaveProfile() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ 
        display_name: displayName || null,
        sync_hour: syncHour,
      });
      onUserUpdate(updated);
      setFeedback({ type: "success", message: "Profile saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save profile";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }



  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setFeedback({ type: "error", message: "Please select an image file" });
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setFeedback({ type: "error", message: "Image must be less than 5MB" });
      return;
    }

    setUploadingAvatar(true);
    setFeedback(null);
    try {
      const result = await uploadAvatar(file);
      onUserUpdate({ ...user, avatar_path: result.avatar_path });
      setFeedback({ type: "success", message: "Avatar uploaded" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to upload avatar";
      setFeedback({ type: "error", message });
    } finally {
      setUploadingAvatar(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleDeleteAvatar() {
    setUploadingAvatar(true);
    setFeedback(null);
    try {
      await deleteAvatar();
      onUserUpdate({ ...user, avatar_path: null });
      setFeedback({ type: "success", message: "Avatar removed" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to remove avatar";
      setFeedback({ type: "error", message });
    } finally {
      setUploadingAvatar(false);
    }
  }

  function getInitials(): string {
    if (displayName) {
      const parts = displayName.trim().split(/\s+/);
      if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
      }
      return parts[0].slice(0, 2).toUpperCase();
    }
    const local = user.email.split("@")[0];
    if (local.includes(".")) {
      const parts = local.split(".");
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return local.slice(0, 2).toUpperCase();
  }



  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Avatar */}
        <div className="flex items-center gap-4">
          <div className="relative">
            {user.avatar_path ? (
              <img
                src={user.avatar_path}
                alt="Avatar"
                className="w-16 h-16 rounded-full object-cover border-2 border-border"
              />
            ) : (
              <div className="w-16 h-16 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xl font-medium">
                {getInitials()}
              </div>
            )}
            {uploadingAvatar && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-full">
                <svg className="w-6 h-6 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleAvatarChange}
              className="hidden"
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingAvatar}
            >
              {user.avatar_path ? "Change photo" : "Upload photo"}
            </Button>
            {user.avatar_path && (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDeleteAvatar}
                disabled={uploadingAvatar}
              >
                Remove
              </Button>
            )}
          </div>
        </div>



        {/* Email (read-only) */}
        <div className="space-y-1.5">
          <Label>Email</Label>
          <Input
            type="email"
            value={user.email}
            disabled
          />
        </div>

        {/* Display name */}
        <div className="space-y-1.5">
          <Label>Display Name</Label>
          <Input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="How you want to be called"
          />
          <p className="text-xs text-muted-foreground">
            This name will be shown in the header and anywhere your profile appears
          </p>
        </div>

        {/* Sync Hour */}
        <div className="space-y-1.5">
          <Label>Daily Sync Time</Label>
          <select
            value={syncHour}
            onChange={(e) => setSyncHour(parseInt(e.target.value))}
            className="w-full h-8 px-2.5 rounded-lg border border-input bg-transparent text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {Array.from({ length: 24 }, (_, i) => (
              <option key={i} value={i}>
                {i.toString().padStart(2, "0")}:00 UTC
              </option>
            ))}
          </select>
          <p className="text-xs text-muted-foreground">
            Your integrations (Garmin, Xert) will sync automatically at this hour
          </p>
        </div>

        <Button onClick={handleSaveProfile} disabled={saving}>
          {saving ? "Saving..." : "Save Profile"}
        </Button>

        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}



function PreferencesSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const { theme, setTheme } = useTheme();

  async function handleToggle() {
    const newSystem = user.unit_system === "metric" ? "imperial" : "metric";
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ unit_system: newSystem });
      onUserUpdate(updated);
      setFeedback({ type: "success", message: "Preferences saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save preferences";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Preferences</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Theme selector */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Theme</p>
            <p className="text-sm text-muted-foreground">
              Choose light, dark, or follow your system preference
            </p>
          </div>
          
          <div className="flex gap-1 bg-muted p-1 rounded-lg">
            {[
              { value: "latte" as Theme, label: "Light", icon: <SunIcon className="w-4 h-4" /> },
              { value: "mocha" as Theme, label: "Dark", icon: <MoonIcon className="w-4 h-4" /> },
              { value: "system" as Theme, label: "System", icon: <MonitorIcon className="w-4 h-4" /> },
            ].map(({ value, label, icon }) => (
              <button
                key={value}
                onClick={() => setTheme(value)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                  theme === value
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {icon}
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Unit system */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Unit System</p>
            <p className="text-sm text-muted-foreground">
              Display distances, elevations, and speeds in {user.unit_system === "metric" ? "kilometers and meters" : "miles and feet"}
            </p>
          </div>
          
          <button
            onClick={handleToggle}
            disabled={saving}
            data-testid="unit-toggle"
            className={cn(
              "relative inline-flex h-9 w-36 items-center rounded-lg transition-colors",
              saving && "opacity-50 cursor-not-allowed",
              user.unit_system === "metric" ? "bg-primary/10" : "bg-success/10"
            )}
          >
            <span
              className={cn(
                "absolute inset-y-1 w-[calc(50%-4px)] rounded-md bg-card shadow transition-transform ml-1",
                user.unit_system === "imperial" && "translate-x-[calc(100%+4px)]"
              )}
            />
            <span className={cn(
              "relative z-10 flex-1 text-center text-sm font-medium transition-colors",
              user.unit_system === "metric" ? "text-primary" : "text-muted-foreground"
            )}>
              Metric
            </span>
            <span className={cn(
              "relative z-10 flex-1 text-center text-sm font-medium transition-colors",
              user.unit_system === "imperial" ? "text-success" : "text-muted-foreground"
            )}>
              Imperial
            </span>
          </button>
        </div>
        
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}



function ThresholdsSection() {
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    effective_date: new Date().toISOString().split("T")[0],
    ftp_watts: "",
    lthr_bpm: "",
    hrmax_bpm: "",
  });
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetchThresholds()
      .then(setThresholds)
      .catch(() => setThresholds([]))
      .finally(() => setLoading(false));
  }, []);

  const currentThreshold = thresholds.length > 0 ? thresholds[0] : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    
    // Check at least one value is provided
    const hasFtp = formData.ftp_watts !== "";
    const hasLthr = formData.lthr_bpm !== "";
    const hasHrmax = formData.hrmax_bpm !== "";
    
    if (!hasFtp && !hasLthr && !hasHrmax) {
      setFeedback({ type: "error", message: "Please enter at least one threshold value" });
      return;
    }
    
    setSaving(true);
    setFeedback(null);
    try {
      const newThreshold = await createThreshold({
        effective_date: formData.effective_date,
        ftp_watts: hasFtp ? parseInt(formData.ftp_watts) : undefined,
        lthr_bpm: hasLthr ? parseInt(formData.lthr_bpm) : undefined,
        hrmax_bpm: hasHrmax ? parseInt(formData.hrmax_bpm) : undefined,
      });
      setThresholds([newThreshold, ...thresholds]);
      setShowForm(false);
      setFormData({
        effective_date: new Date().toISOString().split("T")[0],
        ftp_watts: "",
        lthr_bpm: "",
        hrmax_bpm: "",
      });
      setFeedback({ type: "success", message: "Threshold saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save threshold";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="animate-pulse">
          <div className="h-5 bg-muted rounded w-1/4 mb-4"></div>
          <div className="h-20 bg-muted rounded"></div>
        </CardContent>
      </Card>
    );
  }



  return (
    <Card>
      <CardHeader>
        <CardTitle>Thresholds</CardTitle>
        <CardAction>
          <Button variant="ghost" size="sm" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : currentThreshold ? "Update" : "+ Add"}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Current values */}
        {currentThreshold && (
          <div className="grid grid-cols-3 gap-4 p-4 bg-muted/50 rounded-lg">
            <div>
              <div className="text-xs text-muted-foreground uppercase tracking-wide">FTP</div>
              <div className="text-xl font-bold text-foreground">
                {currentThreshold.ftp_watts ? `${currentThreshold.ftp_watts}W` : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase tracking-wide">LTHR</div>
              <div className="text-xl font-bold text-foreground">
                {currentThreshold.lthr_bpm ? `${currentThreshold.lthr_bpm} bpm` : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase tracking-wide">HRmax</div>
              <div className="text-xl font-bold text-foreground">
                {currentThreshold.max_hr_bpm ? `${currentThreshold.max_hr_bpm} bpm` : "—"}
              </div>
            </div>
          </div>
        )}

        {/* Add/Update form */}
        {showForm && (
          <form onSubmit={handleSubmit} className="p-4 bg-primary/5 rounded-lg space-y-3">
            <p className="text-xs text-muted-foreground mb-2">
              {currentThreshold 
                ? "Enter values to update. Empty fields keep current values (previously set values cannot be removed)."
                : "Enter at least one threshold value. You can add the others later."}
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Effective Date</Label>
                <Input
                  type="date"
                  value={formData.effective_date}
                  onChange={(e) => setFormData({ ...formData, effective_date: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">FTP (watts)</Label>
                <Input
                  type="number"
                  value={formData.ftp_watts}
                  onChange={(e) => setFormData({ ...formData, ftp_watts: e.target.value })}
                  placeholder={currentThreshold?.ftp_watts ? `Current: ${currentThreshold.ftp_watts}` : "e.g. 250"}
                  min="50"
                  max="600"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">LTHR (bpm)</Label>
                <Input
                  type="number"
                  value={formData.lthr_bpm}
                  onChange={(e) => setFormData({ ...formData, lthr_bpm: e.target.value })}
                  placeholder={currentThreshold?.lthr_bpm ? `Current: ${currentThreshold.lthr_bpm}` : "e.g. 165"}
                  min="80"
                  max="220"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">HRmax (bpm)</Label>
                <Input
                  type="number"
                  value={formData.hrmax_bpm}
                  onChange={(e) => setFormData({ ...formData, hrmax_bpm: e.target.value })}
                  placeholder={currentThreshold?.max_hr_bpm ? `Current: ${currentThreshold.max_hr_bpm}` : "e.g. 185"}
                  min="100"
                  max="250"
                />
              </div>
            </div>
            <Button type="submit" disabled={saving} className="w-full">
              {saving ? "Saving..." : "Save Threshold"}
            </Button>
          </form>
        )}



        {/* History table */}
        {thresholds.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground uppercase tracking-wide border-b border-border">
                  <th className="pb-2">Date</th>
                  <th className="pb-2 text-right">FTP</th>
                  <th className="pb-2 text-right">LTHR</th>
                  <th className="pb-2 text-right">HRmax</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {thresholds.map((t, i) => (
                  <tr key={i} className={i === 0 ? "text-foreground font-medium" : "text-muted-foreground"}>
                    <td className="py-2">{new Date(t.effective_date).toLocaleDateString()}</td>
                    <td className="py-2 text-right">{t.ftp_watts ? `${t.ftp_watts}W` : "—"}</td>
                    <td className="py-2 text-right">{t.lthr_bpm ? `${t.lthr_bpm} bpm` : "—"}</td>
                    <td className="py-2 text-right">{t.max_hr_bpm ? `${t.max_hr_bpm} bpm` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {thresholds.length === 0 && !showForm && (
          <p className="text-sm text-muted-foreground">No thresholds configured. Add your first threshold to enable zone calculations.</p>
        )}

        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}



function ZonesSection() {
  const [powerZones, setPowerZones] = useState<PowerZone[]>([]);
  const [hrZones, setHrZones] = useState<HrZone[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedPowerZones, setEditedPowerZones] = useState<PowerZone[]>([]);
  const [editedHrZones, setEditedHrZones] = useState<HrZone[]>([]);

  useEffect(() => {
    fetchZones()
      .then(({ power_zones, hr_zones }) => {
        setPowerZones(power_zones);
        setHrZones(hr_zones);
      })
      .catch(() => {
        setPowerZones([]);
        setHrZones([]);
      })
      .finally(() => setLoading(false));
  }, []);

  function startEdit() {
    setEditedPowerZones([...powerZones]);
    setEditedHrZones([...hrZones]);
    setEditMode(true);
  }

  function cancelEdit() {
    setEditMode(false);
    setFeedback(null);
  }

  async function handleSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const result = await updateZones({
        power_zones: editedPowerZones.map(z => ({
          zone_number: z.zone_number,
          min_value: z.min_watts,
          max_value: z.max_watts ?? undefined,
        })),
        hr_zones: editedHrZones.map(z => ({
          zone_number: z.zone_number,
          min_value: z.min_bpm,
          max_value: z.max_bpm ?? undefined,
        })),
      });
      setPowerZones(result.power_zones);
      setHrZones(result.hr_zones);
      setEditMode(false);
      setFeedback({ type: "success", message: "Zones saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save zones";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }



  async function handleReset() {
    if (!confirm("Reset all zones to defaults based on current thresholds?")) return;
    setSaving(true);
    setFeedback(null);
    try {
      const result = await updateZones({ reset_to_defaults: true });
      setPowerZones(result.power_zones);
      setHrZones(result.hr_zones);
      setEditMode(false);
      setFeedback({ type: "success", message: "Zones reset to defaults" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to reset zones";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  function updatePowerZone(index: number, field: "min_watts" | "max_watts", value: string) {
    const updated = [...editedPowerZones];
    const numVal = parseInt(value) || 0;
    if (field === "max_watts") {
      updated[index] = { ...updated[index], [field]: value === "" ? null : numVal };
    } else {
      updated[index] = { ...updated[index], [field]: numVal };
    }
    setEditedPowerZones(updated);
  }

  function updateHrZone(index: number, field: "min_bpm" | "max_bpm", value: string) {
    const updated = [...editedHrZones];
    const numVal = parseInt(value) || 0;
    if (field === "max_bpm") {
      updated[index] = { ...updated[index], [field]: value === "" ? null : numVal };
    } else {
      updated[index] = { ...updated[index], [field]: numVal };
    }
    setEditedHrZones(updated);
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="animate-pulse">
          <div className="h-5 bg-muted rounded w-1/4 mb-4"></div>
          <div className="h-32 bg-muted rounded"></div>
        </CardContent>
      </Card>
    );
  }

  const displayPowerZones = editMode ? editedPowerZones : powerZones;
  const displayHrZones = editMode ? editedHrZones : hrZones;



  return (
    <Card>
      <CardHeader>
        <CardTitle>Training Zones</CardTitle>
        <CardAction>
          <div className="flex gap-2">
            {editMode ? (
              <>
                <Button variant="ghost" size="sm" onClick={cancelEdit} disabled={saving}>
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSave} disabled={saving}>
                  {saving ? "Saving..." : "Save"}
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" size="sm" onClick={handleReset} disabled={saving || powerZones.length === 0}>
                  Reset
                </Button>
                <Button variant="ghost" size="sm" onClick={startEdit} disabled={powerZones.length === 0}>
                  Edit
                </Button>
              </>
            )}
          </div>
        </CardAction>
      </CardHeader>
      <CardContent>
        {powerZones.length === 0 && hrZones.length === 0 ? (
          <p className="text-sm text-muted-foreground">Add thresholds first to generate training zones.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Power Zones */}
            <div>
              <h3 className="text-sm font-medium text-foreground mb-2">Power Zones</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground uppercase tracking-wide border-b border-border">
                    <th className="pb-2 w-8">Zone</th>
                    <th className="pb-2">Name</th>
                    <th className="pb-2 text-right">Min</th>
                    <th className="pb-2 text-right">Max</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {displayPowerZones.map((z, i) => (
                    <tr key={z.zone_number}>
                      <td className="py-2 font-medium text-foreground">Z{z.zone_number}</td>
                      <td className="py-2 text-muted-foreground">{z.name}</td>
                      <td className="py-2 text-right">
                        {editMode ? (
                          <Input
                            type="number"
                            value={z.min_watts}
                            onChange={(e) => updatePowerZone(i, "min_watts", e.target.value)}
                            className="w-16 text-right"
                          />
                        ) : (
                          <span className="text-foreground">{z.min_watts}W</span>
                        )}
                      </td>
                      <td className="py-2 text-right">
                        {editMode ? (
                          <Input
                            type="number"
                            value={z.max_watts ?? ""}
                            onChange={(e) => updatePowerZone(i, "max_watts", e.target.value)}
                            placeholder="∞"
                            className="w-16 text-right"
                          />
                        ) : (
                          <span className="text-foreground">{z.max_watts ? `${z.max_watts}W` : "∞"}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>



            {/* HR Zones */}
            <div>
              <h3 className="text-sm font-medium text-foreground mb-2">Heart Rate Zones</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground uppercase tracking-wide border-b border-border">
                    <th className="pb-2 w-8">Zone</th>
                    <th className="pb-2">Name</th>
                    <th className="pb-2 text-right">Min</th>
                    <th className="pb-2 text-right">Max</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {displayHrZones.map((z, i) => (
                    <tr key={z.zone_number}>
                      <td className="py-2 font-medium text-foreground">Z{z.zone_number}</td>
                      <td className="py-2 text-muted-foreground">{z.name}</td>
                      <td className="py-2 text-right">
                        {editMode ? (
                          <Input
                            type="number"
                            value={z.min_bpm}
                            onChange={(e) => updateHrZone(i, "min_bpm", e.target.value)}
                            className="w-16 text-right"
                          />
                        ) : (
                          <span className="text-foreground">{z.min_bpm} bpm</span>
                        )}
                      </td>
                      <td className="py-2 text-right">
                        {editMode ? (
                          <Input
                            type="number"
                            value={z.max_bpm ?? ""}
                            onChange={(e) => updateHrZone(i, "max_bpm", e.target.value)}
                            placeholder="∞"
                            className="w-16 text-right"
                          />
                        ) : (
                          <span className="text-foreground">{z.max_bpm ? `${z.max_bpm} bpm` : "∞"}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

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
      .catch(() => {
        setOauthLinks([]);
      })
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
      <Card>
        <CardHeader>
          <CardTitle>Connected Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-muted-foreground">Loading...</div>
        </CardContent>
      </Card>
    );
  }



  return (
    <Card>
      <CardHeader>
        <CardTitle>Connected Accounts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <FeedbackAlert feedback={feedback} />

        {/* Google */}
        <div className="flex items-center justify-between p-4 border border-border rounded-lg">
          <div className="flex items-center gap-3">
            <svg className="w-6 h-6" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            <div>
              <div className="font-medium text-foreground">Google</div>
              {googleLink ? (
                <div className="text-sm text-muted-foreground">{googleLink.provider_email}</div>
              ) : (
                <div className="text-sm text-muted-foreground">Not connected</div>
              )}
            </div>
          </div>
          {googleLink ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleDisconnect("google")}
              disabled={disconnecting === "google" || !canDisconnect}
              title={!canDisconnect ? "Set a password before disconnecting your last OAuth provider" : undefined}
            >
              {disconnecting === "google" ? "Disconnecting..." : "Disconnect"}
            </Button>
          ) : (
            <Button variant="outline" size="sm" asChild>
              <a href="/auth/google/connect">Connect</a>
            </Button>
          )}
        </div>



        {/* GitHub */}
        <div className="flex items-center justify-between p-4 border border-border rounded-lg">
          <div className="flex items-center gap-3">
            <svg className="w-6 h-6 text-foreground" fill="currentColor" viewBox="0 0 24 24">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0012 2z"/>
            </svg>
            <div>
              <div className="font-medium text-foreground">GitHub</div>
              {githubLink ? (
                <div className="text-sm text-muted-foreground">{githubLink.provider_email || githubLink.display_name}</div>
              ) : (
                <div className="text-sm text-muted-foreground">Not connected</div>
              )}
            </div>
          </div>
          {githubLink ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleDisconnect("github")}
              disabled={disconnecting === "github" || !canDisconnect}
              title={!canDisconnect ? "Set a password before disconnecting your last OAuth provider" : undefined}
            >
              {disconnecting === "github" ? "Disconnecting..." : "Disconnect"}
            </Button>
          ) : (
            <Button variant="outline" size="sm" asChild>
              <a href="/auth/github/connect">Connect</a>
            </Button>
          )}
        </div>



        {/* Password section for OAuth-only users */}
        {!userHasPassword && (
          <div className="mt-6 pt-6 border-t border-border">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-medium text-foreground">Password</div>
                <div className="text-sm text-muted-foreground">
                  Set a password to enable email/password login
                </div>
              </div>
              {!showPasswordForm && (
                <Button variant="outline" size="sm" onClick={() => setShowPasswordForm(true)}>
                  Set Password
                </Button>
              )}
            </div>

            {showPasswordForm && (
              <div className="mt-4 space-y-3">
                <Input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="New password (min 8 characters)"
                />
                <Input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm password"
                />
                <div className="flex gap-2">
                  <Button onClick={handleSetPassword} disabled={settingPassword}>
                    {settingPassword ? "Saving..." : "Save Password"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setShowPasswordForm(false);
                      setNewPassword("");
                      setConfirmPassword("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}



function IntegrationsSection() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Integrations</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <XertIntegration />
        <GarminIntegration />
      </CardContent>
    </Card>
  );
}

function XertIntegration() {
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
        setXertStatus({ configured: false, xert_email: null, sync_since: null });
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleConnect() {
    if (!email || !password) return;
    setSaving(true);
    setFeedback(null);
    try {
      await saveMyXertCredentials(email, password, syncSince);
      setXertStatus({ configured: true, xert_email: email, sync_since: syncSince });
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
      setXertStatus({ configured: false, xert_email: null, sync_since: null });
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
      <div className="border border-border rounded-lg p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-muted rounded w-1/4 mb-2"></div>
          <div className="h-10 bg-muted rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">Xert</h3>
          <p className="text-sm text-muted-foreground">
            {xertStatus?.configured
              ? `Connected as ${xertStatus.xert_email}`
              : "Not connected"}
          </p>
        </div>
        <span
          data-testid="xert-status"
          className={cn(
            "px-2 py-1 text-xs font-medium rounded-full",
            xertStatus?.configured
              ? "bg-success/20 text-success"
              : "bg-muted text-muted-foreground"
          )}
        >
          {xertStatus?.configured ? "Connected" : "Not configured"}
        </span>
      </div>


      
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label>Xert Email</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
            data-testid="xert-email"
          />
        </div>
        
        <div className="space-y-1.5">
          <Label>Xert Password</Label>
          <PasswordInput
            value={password}
            onChange={setPassword}
            placeholder={xertStatus?.configured ? "Enter new password to update" : "Enter password"}
            data-testid="xert-password"
          />
        </div>
        
        <div className="space-y-1.5">
          <Label>Sync activities since</Label>
          <Input
            type="date"
            value={syncSince}
            onChange={(e) => setSyncSince(e.target.value)}
            data-testid="xert-sync-since"
          />
          <p className="text-xs text-muted-foreground">
            Activities from this date onwards will be imported
          </p>
        </div>
        
        <div className="flex gap-3 pt-2">
          <Button
            onClick={handleConnect}
            disabled={saving || !email || !password}
            data-testid="xert-connect"
          >
            {saving ? "Connecting..." : xertStatus?.configured ? "Update" : "Connect"}
          </Button>
          
          {xertStatus?.configured && (
            <>
              <SyncButton onSync={triggerXertSync} label="Sync Now" />
              <Button
                variant="destructive"
                onClick={handleDisconnect}
                disabled={saving}
                data-testid="xert-disconnect"
              >
                Disconnect
              </Button>
            </>
          )}
        </div>
      </div>
      
      <FeedbackAlert feedback={feedback} />
    </div>
  );
}



function GarminIntegration() {
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
        setGarminStatus({ configured: false, garmin_email: null, sync_since: null });
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
        setGarminStatus({ configured: true, garmin_email: email, sync_since: syncSince });
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
      setGarminStatus({ configured: true, garmin_email: email, sync_since: syncSince });
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
      setGarminStatus({ configured: false, garmin_email: null, sync_since: null });
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

  if (loading) {
    return (
      <div className="border border-border rounded-lg p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-muted rounded w-1/4 mb-2"></div>
          <div className="h-10 bg-muted rounded"></div>
        </div>
      </div>
    );
  }



  return (
    <div className="border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">Garmin</h3>
          <p className="text-sm text-muted-foreground">
            {garminStatus?.configured
              ? `Connected as ${garminStatus.garmin_email}`
              : "Not connected"}
          </p>
        </div>
        <span
          data-testid="garmin-status"
          className={cn(
            "px-2 py-1 text-xs font-medium rounded-full",
            garminStatus?.configured
              ? "bg-success/20 text-success"
              : "bg-muted text-muted-foreground"
          )}
        >
          {garminStatus?.configured ? "Connected" : "Not configured"}
        </span>
      </div>
      
      {mfaRequired ? (
        <MfaForm
          mfaCode={mfaCode}
          setMfaCode={setMfaCode}
          saving={saving}
          onSubmit={handleMfaSubmit}
          onCancel={handleCancelMfa}
        />
      ) : (
        <GarminCredentialsForm
          email={email}
          setEmail={setEmail}
          password={password}
          setPassword={setPassword}
          syncSince={syncSince}
          setSyncSince={setSyncSince}
          saving={saving}
          configured={garminStatus?.configured ?? false}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
        />
      )}
      
      <FeedbackAlert feedback={feedback} />
    </div>
  );
}



function MfaForm({
  mfaCode,
  setMfaCode,
  saving,
  onSubmit,
  onCancel,
}: {
  mfaCode: string;
  setMfaCode: (v: string) => void;
  saving: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label>MFA Code</Label>
        <Input
          type="text"
          value={mfaCode}
          onChange={(e) => setMfaCode(e.target.value)}
          placeholder="Enter 6-digit code"
          data-testid="garmin-mfa-code"
          autoComplete="one-time-code"
        />
        <p className="text-xs text-muted-foreground">
          Enter the code from your Garmin authenticator app or email
        </p>
      </div>
      
      <div className="flex gap-3 pt-2">
        <Button onClick={onSubmit} disabled={saving || !mfaCode} data-testid="garmin-mfa-submit">
          {saving ? "Verifying..." : "Verify"}
        </Button>
        <Button variant="outline" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </div>
  );
}



function GarminCredentialsForm({
  email,
  setEmail,
  password,
  setPassword,
  syncSince,
  setSyncSince,
  saving,
  configured,
  onConnect,
  onDisconnect,
}: {
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  syncSince: string;
  setSyncSince: (v: string) => void;
  saving: boolean;
  configured: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label>Garmin Email</Label>
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="your@email.com"
          data-testid="garmin-email"
        />
      </div>
      
      <div className="space-y-1.5">
        <Label>Garmin Password</Label>
        <PasswordInput
          value={password}
          onChange={setPassword}
          placeholder={configured ? "Enter new password to update" : "Enter password"}
          data-testid="garmin-password"
        />
      </div>
      
      <div className="space-y-1.5">
        <Label>Sync activities since</Label>
        <Input
          type="date"
          value={syncSince}
          onChange={(e) => setSyncSince(e.target.value)}
          data-testid="garmin-sync-since"
        />
        <p className="text-xs text-muted-foreground">
          Activities from this date onwards will be imported
        </p>
      </div>
      
      <div className="flex gap-3 pt-2">
        <Button onClick={onConnect} disabled={saving || !email || !password} data-testid="garmin-connect">
          {saving ? "Connecting..." : configured ? "Update" : "Connect"}
        </Button>
        
        {configured && (
          <>
            <SyncButton onSync={triggerGarminSync} label="Sync Now" />
            <Button
              variant="destructive"
              onClick={onDisconnect}
              disabled={saving}
              data-testid="garmin-disconnect"
            >
              Disconnect
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
