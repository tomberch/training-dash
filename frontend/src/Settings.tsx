import { useState, useEffect, useRef, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";
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
  uploadAvatar,
  deleteAvatar,
  triggerGarminSync,
  triggerXertSync,
  fetchOAuthLinks,
  disconnectOAuthProvider,
  setPassword,
  hasPassword,
  fetchCurrentMetrics,
  ApiError,
} from "./api";
import type { 
  User, 
  XertCredentialsStatus, 
  GarminCredentialsStatus,
  OAuthLink,
} from "./api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent, CardAction } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  DEFAULT_POWER_ZONES,
  DEFAULT_HR_ZONES,
  computePowerZones,
  computeHrZones,
  type ZonePercentages,
} from "@/lib/zones";
import { POWER_ZONE_COLORS, HR_ZONE_COLORS } from "@/constants";
import { useTheme } from "./hooks/useTheme";
import type { Theme } from "./hooks/useTheme";
import { SunIcon, MoonIcon, MonitorIcon, SparklesIcon } from "./components/icons/ThemeIcons";
import { PageHeader } from "./components/PageHeader";

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
        className="h-11 px-4 pr-10 text-base md:text-base"
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
  onUserUpdate: (user: User) => void;
}



export function Settings({ user, onUserUpdate }: SettingsProps) {
  const location = useLocation();

  // Scroll to section when URL has hash (e.g., /settings#power-heart-rate)
  useEffect(() => {
    if (location.hash) {
      const elementId = location.hash.slice(1); // Remove '#'
      const element = document.getElementById(elementId);
      if (element) {
        // Small delay to ensure DOM is rendered
        setTimeout(() => {
          element.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 100);
      }
    }
  }, [location.hash]);

  return (
    <div className="p-8">
      {/* Full-width header */}
      <PageHeader
        title="Settings"
        subtitle="Manage your profile, preferences, and integrations"
      />
      
      {/* Content area */}
      <div className="space-y-6">
        <ProfileSection user={user} onUserUpdate={onUserUpdate} />
        <PreferencesSection user={user} onUserUpdate={onUserUpdate} />
        <MapSection user={user} onUserUpdate={onUserUpdate} />
        <PowerHeartRateSection user={user} onUserUpdate={onUserUpdate} />
        <ConnectedAccountsSection />
        <ZonesSection user={user} onUserUpdate={onUserUpdate} />
        <IntegrationsSection />
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
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          Profile
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Avatar + Form side by side */}
        <div className="flex items-start gap-6 mb-6">
          {/* Avatar */}
          <div className="relative flex-shrink-0">
            {user.avatar_path ? (
              <img
                src={user.avatar_path}
                alt="Avatar"
                className="w-24 h-24 rounded-full object-cover"
              />
            ) : (
              <div className="w-24 h-24 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-3xl font-bold">
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
              className="mt-2"
            >
              {user.avatar_path ? "Change photo" : "Upload photo"}
            </Button>
            {user.avatar_path && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDeleteAvatar}
                disabled={uploadingAvatar}
                className="mt-1 text-destructive hover:text-destructive"
              >
                Remove
              </Button>
            )}
          </div>

          {/* Form fields */}
          <div className="flex-1 space-y-4">
            {/* Email (read-only) */}
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Email</Label>
              <Input
                type="email"
                value={user.email}
                disabled
                className="h-11 px-4 text-base md:text-base"
              />
            </div>

            {/* Display name */}
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Display Name</Label>
              <Input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="How you want to be called"
                className="h-11 px-4 text-base md:text-base"
              />
              <p className="text-caption">
                This name will be shown in the header and anywhere your profile appears
              </p>
            </div>

            {/* Sync Hour */}
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Daily Sync Time</Label>
              <select
                value={syncHour}
                onChange={(e) => setSyncHour(parseInt(e.target.value))}
                className="w-full h-11 px-4 rounded-lg border border-input bg-transparent text-base focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {Array.from({ length: 24 }, (_, i) => (
                  <option key={i} value={i}>
                    {i.toString().padStart(2, "0")}:00 UTC
                  </option>
                ))}
              </select>
              <p className="text-caption">
                Your integrations (Garmin, Xert) will sync automatically at this hour
              </p>
            </div>
          </div>
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
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
          </svg>
          Preferences
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Theme selector */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium mb-1">Theme</h3>
            <p className="text-body-secondary">
              Choose light, dark, or follow your system preference
            </p>
          </div>
          
          <div className="flex bg-muted rounded-lg p-1">
            {[
              { value: "latte" as Theme, label: "Light", icon: <SunIcon className="w-4 h-4" /> },
              { value: "mocha" as Theme, label: "Dark", icon: <MoonIcon className="w-4 h-4" /> },
              { value: "midnight" as Theme, label: "Midnight", icon: <SparklesIcon className="w-4 h-4" /> },
              { value: "system" as Theme, label: "System", icon: <MonitorIcon className="w-4 h-4" /> },
            ].map(({ value, label, icon }) => (
              <button
                key={value}
                onClick={() => setTheme(value)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                  theme === value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {icon}
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Unit system */}
        <div className="flex items-center justify-between pt-6 border-t border-border">
          <div>
            <h3 className="font-medium mb-1">Unit System</h3>
            <p className="text-body-secondary">
              Display distances, elevations, and speeds in kilometers or miles
            </p>
          </div>
          
          <div className="flex bg-muted rounded-lg p-1">
            <button
              onClick={() => user.unit_system !== "metric" && handleToggle()}
              disabled={saving}
              className={cn(
                "px-4 py-2 rounded-md text-sm font-medium transition-colors",
                user.unit_system === "metric"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              Metric
            </button>
            <button
              onClick={() => user.unit_system !== "imperial" && handleToggle()}
              disabled={saving}
              className={cn(
                "px-4 py-2 rounded-md text-sm font-medium transition-colors",
                user.unit_system === "imperial"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              Imperial
            </button>
          </div>
        </div>
        
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}


// Map tile style options with preview images
const MAP_TILE_STYLES = [
  {
    value: "osm" as const,
    label: "OpenStreetMap",
    preview: "/map-previews/osm.png",
  },
  {
    value: "positron" as const,
    label: "Positron",
    preview: "/map-previews/positron.png",
  },
  {
    value: "dark_matter" as const,
    label: "Dark Matter",
    preview: "/map-previews/dark_matter.png",
  },
  {
    value: "voyager" as const,
    label: "Voyager",
    preview: "/map-previews/voyager.png",
  },
];

function MapSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  async function handleStyleChange(style: typeof user.map_tile_style) {
    if (style === user.map_tile_style) return;
    
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ map_tile_style: style });
      onUserUpdate(updated);
      setFeedback({ type: "success", message: "Map style updated" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to update map style";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Map
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <h3 className="font-medium mb-1">Map Style</h3>
          <p className="text-body-secondary">
            Choose how maps appear throughout the app
          </p>
        </div>

        {/* 2x2 grid of style cards */}
        <div className="grid grid-cols-2 gap-3 max-w-2xl">
          {MAP_TILE_STYLES.map(({ value, label, preview }) => {
            const isSelected = user.map_tile_style === value;
            return (
              <button
                key={value}
                onClick={() => handleStyleChange(value)}
                disabled={saving}
                className={cn(
                  "relative rounded-lg overflow-hidden border-2 transition-all text-left aspect-[16/7]",
                  isSelected
                    ? "border-primary ring-2 ring-primary/20"
                    : "border-border hover:border-muted-foreground/50",
                  saving && "opacity-50 cursor-not-allowed"
                )}
              >
                {/* Preview image */}
                <img
                  src={preview}
                  alt={`${label} map style preview`}
                  className="absolute inset-0 w-full h-full object-cover"
                />
                
                {/* Label overlaid on image */}
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-2 py-1.5">
                  <span className="text-sm font-medium text-white">{label}</span>
                </div>

                {/* Checkmark badge for selected */}
                {isSelected && (
                  <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-primary flex items-center justify-center shadow-md">
                    <svg className="w-3 h-3 text-primary-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
              </button>
            );
          })}
        </div>

        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}


function PowerHeartRateSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const hrPowerModel = user.hr_power_model;
  const minRidesRequired = 5;
  const rideCount = hrPowerModel?.ride_count ?? 0;
  const modelReady = rideCount >= minRidesRequired;
  const isEnabled = user.hr_derived_power_enabled;

  async function handleToggle() {
    if (!modelReady) return;
    
    const newValue = !isEnabled;
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ hr_derived_power_enabled: newValue });
      onUserUpdate(updated);
      setFeedback({ 
        type: "success", 
        message: newValue ? "HR-derived power enabled" : "HR-derived power disabled" 
      });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to update setting";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  // Format confidence as percentage
  const confidencePercent = hrPowerModel?.confidence 
    ? Math.round(hrPowerModel.confidence * 100) 
    : null;

  // Format confidence level label
  const confidenceLabel = confidencePercent !== null
    ? confidencePercent >= 80 ? "High" : confidencePercent >= 60 ? "Medium" : "Low"
    : null;

  return (
    <Card id="power-heart-rate" className="card-hover">
      <CardHeader>
        <div className="flex items-center justify-between w-full">
          <CardTitle className="flex items-center gap-2 text-card-title">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
            Power & Heart Rate
          </CardTitle>
          {/* Toggle in header like mockup */}
          <button
            onClick={handleToggle}
            disabled={saving || !modelReady}
            aria-pressed={isEnabled}
            className={cn(
              "relative inline-flex h-6 w-12 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
              isEnabled ? "bg-primary" : "bg-muted",
              (!modelReady || saving) && "opacity-50 cursor-not-allowed"
            )}
          >
            <span
              className={cn(
                "pointer-events-none absolute left-1 bottom-1 w-4 h-4 transform rounded-full bg-muted-foreground shadow transition duration-200 ease-in-out",
                isEnabled ? "translate-x-6 bg-white" : "translate-x-0"
              )}
            />
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <div>
          <h3 className="font-medium mb-2">HR-Derived Power</h3>
          <p className="text-body-secondary mb-4">
            Estimate power from heart rate on activities without a power meter.
            Uses an Efficiency Factor model trained from your dual-sensor rides.
          </p>
          
          {!modelReady && (
            <div className="bg-primary/10 border border-primary/30 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm text-foreground mb-1">Requirement not met</p>
                  <p className="text-caption">
                    Record {minRidesRequired - rideCount} more {minRidesRequired - rideCount === 1 ? "activity" : "activities"} with both power meter and heart rate to enable this feature.
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-primary rounded-full transition-all" 
                        style={{ width: `${(rideCount / minRidesRequired) * 100}%` }}
                      />
                    </div>
                    <span className="text-caption">{rideCount}/{minRidesRequired}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {modelReady && hrPowerModel?.model_exists && (
            <div className="p-3 rounded-lg bg-muted/50 text-sm">
              <div className="flex items-center gap-4 text-muted-foreground">
                <span>Model trained on <span className="font-medium text-foreground">{rideCount}</span> rides</span>
                {confidenceLabel && (
                  <span className={cn(
                    "px-2 py-0.5 rounded-full text-xs font-medium",
                    confidencePercent && confidencePercent >= 80 
                      ? "bg-success/20 text-success" 
                      : confidencePercent && confidencePercent >= 60
                        ? "bg-warning/20 text-warning"
                        : "bg-muted text-muted-foreground"
                  )}>
                    {confidenceLabel} confidence
                  </span>
                )}
              </div>
              {hrPowerModel.is_stale && (
                <p className="text-warning mt-2 text-xs">
                  Model may be outdated. Record new dual-sensor activities to improve accuracy.
                </p>
              )}
            </div>
          )}
        </div>
        
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}


function ZonesSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  // Fetch current FTP and LTHR from metrics API
  const [ftp, setFtp] = useState<number | null>(null);
  const [lthr, setLthr] = useState<number | null>(null);
  const [loadingThresholds, setLoadingThresholds] = useState(true);
  
  const loadThresholds = useCallback(async () => {
    try {
      const currentMetrics = await fetchCurrentMetrics();
      setFtp(currentMetrics.ftp?.value ?? null);
      setLthr(currentMetrics.lthr?.value ?? null);
    } catch (err) {
      console.error("Failed to load thresholds:", err);
    } finally {
      setLoadingThresholds(false);
    }
  }, []);
  
  useEffect(() => {
    loadThresholds();
  }, [loadThresholds]);
  
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  
  // Current percentages from user or defaults
  const powerPercentages = user.power_zone_percentages ?? DEFAULT_POWER_ZONES;
  const hrPercentages = user.hr_zone_percentages ?? DEFAULT_HR_ZONES;
  
  // Edited values (only used in edit mode)
  const [editedPowerPct, setEditedPowerPct] = useState<ZonePercentages>(powerPercentages);
  const [editedHrPct, setEditedHrPct] = useState<ZonePercentages>(hrPercentages);
  
  // Compute zones from percentages and thresholds
  const displayPowerPct = editMode ? editedPowerPct : powerPercentages;
  const displayHrPct = editMode ? editedHrPct : hrPercentages;
  const powerZones = computePowerZones(ftp ?? 0, displayPowerPct);
  const hrZones = computeHrZones(lthr ?? 0, displayHrPct);
  
  function startEdit() {
    setEditedPowerPct({ ...powerPercentages });
    setEditedHrPct({ ...hrPercentages });
    setEditMode(true);
    setFeedback(null);
  }
  
  function cancelEdit() {
    setEditMode(false);
    setFeedback(null);
  }
  
  async function handleSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({
        power_zone_percentages: editedPowerPct,
        hr_zone_percentages: editedHrPct,
      });
      onUserUpdate(updated);
      setEditMode(false);
      setFeedback({ type: "success", message: "Zone settings saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save zones";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }
  
  function resetPowerZones() {
    setEditedPowerPct({ ...DEFAULT_POWER_ZONES });
  }
  
  function resetHrZones() {
    setEditedHrPct({ ...DEFAULT_HR_ZONES });
  }
  
  function updatePowerPct(zone: string, field: "min" | "max", value: string) {
    const numVal = parseInt(value) || 0;
    setEditedPowerPct(prev => ({
      ...prev,
      [zone]: field === "min" 
        ? [numVal, prev[zone][1]]
        : [prev[zone][0], value === "" ? null : numVal],
    }));
  }
  
  function updateHrPct(zone: string, field: "min" | "max", value: string) {
    const numVal = parseInt(value) || 0;
    setEditedHrPct(prev => ({
      ...prev,
      [zone]: field === "min"
        ? [numVal, prev[zone][1]]
        : [prev[zone][0], value === "" ? null : numVal],
    }));
  }
  
  // Check if user has thresholds set
  const hasFtp = ftp !== null && ftp > 0;
  const hasLthr = lthr !== null && lthr > 0;
  const showThresholdWarning = !hasFtp || !hasLthr;

  if (loadingThresholds) {
    return (
      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-card-title">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Training Zones
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[200px] w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      {/* Warning outside the card when thresholds not set */}
      {showThresholdWarning && (
        <div className="bg-warning/10 border border-warning/30 rounded-xl p-5 mb-6">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-semibold text-foreground mb-1">Threshold Required</p>
              <p className="text-sm text-muted-foreground">
                Set your {!hasFtp && !hasLthr ? "FTP and LTHR thresholds" : !hasFtp ? "FTP threshold" : "LTHR threshold"} to see computed zones. 
                Until then, you can customize zone names and percentages.
              </p>
              <Link 
                to="/athlete?tab=thresholds" 
                className="inline-flex items-center gap-1 text-primary hover:text-primary/80 text-sm font-medium mt-2"
              >
                <span>Go to Athlete → Thresholds</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </Link>
            </div>
          </div>
        </div>
      )}

      <Card className={cn("card-hover relative", editMode && "border-2 border-primary/50")}>
        {/* Edit mode indicator badge */}
        {editMode && (
          <div className="absolute top-0 right-0 bg-primary text-primary-foreground px-4 py-2 rounded-bl-xl rounded-tr-lg text-sm font-medium">
            Editing Zones
          </div>
        )}
        
        <CardHeader className={cn(editMode && "pt-12")}>
          <CardTitle className="flex items-center gap-2 text-card-title">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Training Zones
          </CardTitle>
          <CardAction>
            <div className="flex gap-2">
              {editMode ? (
                <>
                  <Button variant="ghost" size="sm" onClick={cancelEdit} disabled={saving}>
                    Cancel
                  </Button>
                  <Button size="sm" onClick={handleSave} disabled={saving}>
                    {saving ? "Saving..." : "Save Changes"}
                  </Button>
                </>
              ) : (
                <Button variant="ghost" size="sm" onClick={startEdit}>
                  Edit
                </Button>
              )}
            </div>
          </CardAction>
        </CardHeader>
        <CardContent className="space-y-8">
          {/* Power Zones */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <h3 className="text-lg font-semibold text-foreground">Power Zones</h3>
              <span className="text-sm text-muted-foreground ml-2">Based on FTP threshold</span>
            </div>
            
            <div className="bg-muted/30 rounded-lg overflow-hidden border border-border">
              {/* Table Header */}
              <div className="grid grid-cols-12 gap-4 px-4 py-3 bg-muted text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <div className="col-span-1">Zone</div>
                <div className="col-span-3">Name</div>
                <div className="col-span-3">% FTP</div>
                <div className="col-span-3">Watts</div>
                <div className="col-span-2">Color</div>
              </div>
              
              {/* Zone rows */}
              {powerZones.map((z) => {
                const zoneKey = z.zone.toString();
                const color = POWER_ZONE_COLORS[zoneKey];
                return (
                  <div key={z.zone} className="grid grid-cols-12 gap-4 px-4 py-3 border-t border-border items-center hover:bg-muted/50 transition">
                    <div className="col-span-1">
                      <span 
                        className="inline-flex items-center justify-center w-8 h-8 rounded-full text-white font-bold text-sm"
                        style={{ backgroundColor: color }}
                      >
                        {z.zone}
                      </span>
                    </div>
                    <div className="col-span-3">
                      <span className="text-sm text-foreground">{z.name}</span>
                    </div>
                    <div className="col-span-3">
                      {editMode ? (
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            value={editedPowerPct[zoneKey][0]}
                            onChange={(e) => updatePowerPct(zoneKey, "min", e.target.value)}
                            className="w-16 h-9 text-sm text-right"
                          />
                          <span className="text-muted-foreground">-</span>
                          <Input
                            type="number"
                            value={editedPowerPct[zoneKey][1] ?? ""}
                            onChange={(e) => updatePowerPct(zoneKey, "max", e.target.value)}
                            placeholder="∞"
                            className="w-16 h-9 text-sm text-right"
                          />
                          <span className="text-xs text-muted-foreground">%</span>
                        </div>
                      ) : (
                        <span className="text-sm text-foreground">{z.minPct}-{z.maxPct ?? "∞"}%</span>
                      )}
                    </div>
                    <div className="col-span-3">
                      <div className="flex flex-col">
                        <span className="text-sm text-foreground">
                          {hasFtp ? `${z.minValue}-${z.maxValue ?? "∞"} W` : "— W"}
                        </span>
                        {editMode && !hasFtp && (
                          <span className="text-xs text-muted-foreground">Set FTP to calculate</span>
                        )}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <div 
                        className="w-6 h-6 rounded border border-border"
                        style={{ backgroundColor: color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            
            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <p>Power zones use Coggan's 7-zone model. Customize names and ranges as needed.</p>
              {editMode && (
                <button 
                  onClick={resetPowerZones}
                  className="text-primary hover:text-primary/80 font-medium"
                >
                  Reset to defaults
                </button>
              )}
            </div>
          </div>

          {/* HR Zones */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <svg className="w-5 h-5 text-pink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
              <h3 className="text-lg font-semibold text-foreground">Heart Rate Zones</h3>
              <span className="text-sm text-muted-foreground ml-2">Based on LTHR threshold</span>
            </div>
            
            <div className="bg-muted/30 rounded-lg overflow-hidden border border-border">
              {/* Table Header */}
              <div className="grid grid-cols-12 gap-4 px-4 py-3 bg-muted text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <div className="col-span-1">Zone</div>
                <div className="col-span-3">Name</div>
                <div className="col-span-3">% LTHR</div>
                <div className="col-span-3">BPM</div>
                <div className="col-span-2">Color</div>
              </div>
              
              {/* Zone rows */}
              {hrZones.map((z) => {
                const zoneKey = z.zone.toString();
                const color = HR_ZONE_COLORS[zoneKey];
                return (
                  <div key={z.zone} className="grid grid-cols-12 gap-4 px-4 py-3 border-t border-border items-center hover:bg-muted/50 transition">
                    <div className="col-span-1">
                      <span 
                        className="inline-flex items-center justify-center w-8 h-8 rounded-full text-white font-bold text-sm"
                        style={{ backgroundColor: color }}
                      >
                        {z.zone}
                      </span>
                    </div>
                    <div className="col-span-3">
                      <span className="text-sm text-foreground">{z.name}</span>
                    </div>
                    <div className="col-span-3">
                      {editMode ? (
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            value={editedHrPct[zoneKey][0]}
                            onChange={(e) => updateHrPct(zoneKey, "min", e.target.value)}
                            className="w-16 h-9 text-sm text-right"
                          />
                          <span className="text-muted-foreground">-</span>
                          <Input
                            type="number"
                            value={editedHrPct[zoneKey][1] ?? ""}
                            onChange={(e) => updateHrPct(zoneKey, "max", e.target.value)}
                            placeholder="∞"
                            className="w-16 h-9 text-sm text-right"
                          />
                          <span className="text-xs text-muted-foreground">%</span>
                        </div>
                      ) : (
                        <span className="text-sm text-foreground">{z.minPct}-{z.maxPct ?? "∞"}%</span>
                      )}
                    </div>
                    <div className="col-span-3">
                      <div className="flex flex-col">
                        <span className="text-sm text-foreground">
                          {hasLthr ? `${z.minValue}-${z.maxValue ?? "∞"} bpm` : "— bpm"}
                        </span>
                        {editMode && !hasLthr && (
                          <span className="text-xs text-muted-foreground">Set LTHR to calculate</span>
                        )}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <div 
                        className="w-6 h-6 rounded border border-border"
                        style={{ backgroundColor: color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            
            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <p>Heart rate zones use the Friel method. Adjust percentages to match your training methodology.</p>
              {editMode && (
                <button 
                  onClick={resetHrZones}
                  className="text-primary hover:text-primary/80 font-medium"
                >
                  Reset to defaults
                </button>
              )}
            </div>
          </div>

          <FeedbackAlert feedback={feedback} />
        </CardContent>
      </Card>
    </>
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
      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-card-title">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            Connected Accounts
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Google skeleton */}
          <div className="flex items-center justify-between p-4 border border-border rounded-lg">
            <div className="flex items-center gap-3">
              <Skeleton className="h-6 w-6 rounded" />
              <div>
                <Skeleton className="h-4 w-20 mb-1" />
                <Skeleton className="h-3 w-32" />
              </div>
            </div>
            <Skeleton className="h-9 w-24" />
          </div>
          {/* GitHub skeleton */}
          <div className="flex items-center justify-between p-4 border border-border rounded-lg">
            <div className="flex items-center gap-3">
              <Skeleton className="h-6 w-6 rounded" />
              <div>
                <Skeleton className="h-4 w-20 mb-1" />
                <Skeleton className="h-3 w-32" />
              </div>
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
          Connected Accounts
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
              <h3 className="font-medium">Google</h3>
              {googleLink ? (
                <p className="text-body-secondary">{googleLink.provider_email}</p>
              ) : (
                <p className="text-body-secondary">Not connected</p>
              )}
            </div>
          </div>
          {googleLink ? (
            <button
              onClick={() => handleDisconnect("google")}
              disabled={disconnecting === "google" || !canDisconnect}
              title={!canDisconnect ? "Set a password before disconnecting your last OAuth provider" : undefined}
              className="bg-destructive/10 text-destructive hover:bg-destructive/20 px-4 py-2 rounded-lg transition text-sm font-medium disabled:opacity-50"
            >
              {disconnecting === "google" ? "..." : "Disconnect"}
            </button>
          ) : (
            <a
              href="/auth/google/connect"
              className="bg-muted hover:bg-muted/80 border border-border px-4 py-2 rounded-lg transition text-sm font-medium"
            >
              Connect
            </a>
          )}
        </div>

        {/* GitHub */}
        <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-background rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
            </div>
            <div>
              <h3 className="font-medium">GitHub</h3>
              {githubLink ? (
                <p className="text-body-secondary">{githubLink.provider_email || githubLink.display_name}</p>
              ) : (
                <p className="text-body-secondary">Not connected</p>
              )}
            </div>
          </div>
          {githubLink ? (
            <button
              onClick={() => handleDisconnect("github")}
              disabled={disconnecting === "github" || !canDisconnect}
              title={!canDisconnect ? "Set a password before disconnecting your last OAuth provider" : undefined}
              className="bg-destructive/10 text-destructive hover:bg-destructive/20 px-4 py-2 rounded-lg transition text-sm font-medium disabled:opacity-50"
            >
              {disconnecting === "github" ? "..." : "Disconnect"}
            </button>
          ) : (
            <a
              href="/auth/github/connect"
              className="bg-muted hover:bg-muted/80 border border-border px-4 py-2 rounded-lg transition text-sm font-medium"
            >
              Connect
            </a>
          )}
        </div>



        {/* Password section for OAuth-only users */}
        {!userHasPassword && (
          <div className="mt-6 pt-6 border-t border-border">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-medium text-foreground">Password</div>
                <div className="text-body-secondary">
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
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
          </svg>
          Integrations
        </CardTitle>
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
      <div className="border border-border rounded-lg p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-muted rounded w-1/4 mb-2"></div>
          <div className="h-10 bg-muted rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold">Xert</h3>
          <p className="text-body-secondary">
            {xertStatus?.configured
              ? `Connected as ${xertStatus.xert_email}`
              : "Not connected"}
          </p>
        </div>
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


      
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label className="text-muted-foreground">Xert Email</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
            data-testid="xert-email"
            className="h-11 px-4 text-base md:text-base"
          />
        </div>
        
        <div className="space-y-1.5">
          <Label className="text-muted-foreground">Xert Password</Label>
          <PasswordInput
            value={password}
            onChange={setPassword}
            placeholder={xertStatus?.configured ? "Enter new password to update" : "Enter password"}
            data-testid="xert-password"
          />
        </div>
        
        <div className="space-y-1.5">
          <Label className="text-muted-foreground">Sync activities since</Label>
          <Input
            type="date"
            value={syncSince}
            onChange={(e) => setSyncSince(e.target.value)}
            data-testid="xert-sync-since"
            className="h-11 px-4 text-base md:text-base"
          />
          <p className="text-caption">
            Activities from this date onwards will be imported
          </p>
        </div>
        
        {xertStatus?.configured ? (
          <>
            {/* Sync toggle */}
            <div className="flex items-center justify-between py-3 border-t border-border">
              <div>
                <p className="font-medium text-sm">Auto-sync from Xert</p>
                <p className="text-caption">Automatically import new activities at your daily sync time</p>
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
                <span
                  className={cn(
                    "pointer-events-none absolute left-1 bottom-1 w-4 h-4 transform rounded-full bg-muted-foreground shadow transition duration-200 ease-in-out",
                    xertStatus.sync_enabled ? "translate-x-6 bg-white" : "translate-x-0"
                  )}
                />
              </button>
            </div>
            
            <div className="flex gap-3 pt-2">
              <Button
                onClick={handleConnect}
                disabled={saving || !email || !password}
                data-testid="xert-connect"
              >
                {saving ? "Updating..." : "Update"}
              </Button>
              <SyncButton onSync={triggerXertSync} label="Sync Now" />
              <Button
                variant="destructive"
                onClick={handleDisconnect}
                disabled={saving}
                data-testid="xert-disconnect"
              >
                Disconnect
              </Button>
            </div>
          </>
        ) : (
          <Button
            onClick={handleConnect}
            disabled={saving || !email || !password}
            data-testid="xert-connect"
            className="w-full"
          >
            {saving ? "Connecting..." : "Connect"}
          </Button>
        )}
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
      <div className="border border-border rounded-lg p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-muted rounded w-1/4 mb-2"></div>
          <div className="h-10 bg-muted rounded"></div>
        </div>
      </div>
    );
  }



  return (
    <div className="border border-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold">Garmin</h3>
          <p className="text-body-secondary">
            {garminStatus?.configured
              ? `Connected as ${garminStatus.garmin_email}`
              : "Not connected"}
          </p>
        </div>
        <span
          data-testid="garmin-status"
          className={cn(
            "px-3 py-1 text-xs rounded-full",
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
          syncEnabled={garminStatus?.sync_enabled ?? true}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
          onToggleSync={handleToggleSync}
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
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label className="text-muted-foreground">MFA Code</Label>
        <Input
          type="text"
          value={mfaCode}
          onChange={(e) => setMfaCode(e.target.value)}
          placeholder="Enter 6-digit code"
          data-testid="garmin-mfa-code"
          autoComplete="one-time-code"
          className="h-11 px-4 text-base md:text-base"
        />
        <p className="text-caption">
          Enter the code from your Garmin authenticator app or email
        </p>
      </div>
      
      <div className="flex gap-3">
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
  syncEnabled,
  onConnect,
  onDisconnect,
  onToggleSync,
}: {
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  syncSince: string;
  setSyncSince: (v: string) => void;
  saving: boolean;
  configured: boolean;
  syncEnabled: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onToggleSync: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label className="text-muted-foreground">Garmin Email</Label>
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="your@email.com"
          data-testid="garmin-email"
          className="h-11 px-4 text-base md:text-base"
        />
      </div>
      
      <div className="space-y-1.5">
        <Label className="text-muted-foreground">Garmin Password</Label>
        <PasswordInput
          value={password}
          onChange={setPassword}
          placeholder={configured ? "Enter new password to update" : "Enter password"}
          data-testid="garmin-password"
        />
      </div>
      
      <div className="space-y-1.5">
        <Label className="text-muted-foreground">Sync activities since</Label>
        <Input
          type="date"
          value={syncSince}
          onChange={(e) => setSyncSince(e.target.value)}
          data-testid="garmin-sync-since"
          className="h-11 px-4 text-base md:text-base"
        />
        <p className="text-caption">
          Activities from this date onwards will be imported
        </p>
      </div>
      
      {configured ? (
        <>
          {/* Sync toggle */}
          <div className="flex items-center justify-between py-3 border-t border-border">
            <div>
              <p className="font-medium text-sm">Auto-sync from Garmin</p>
              <p className="text-caption">Automatically import new activities at your daily sync time</p>
            </div>
            <button
              onClick={onToggleSync}
              disabled={saving}
              aria-pressed={syncEnabled}
              className={cn(
                "relative inline-flex h-6 w-12 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
                syncEnabled ? "bg-primary" : "bg-muted",
                saving && "opacity-50 cursor-not-allowed"
              )}
            >
              <span
                className={cn(
                  "pointer-events-none absolute left-1 bottom-1 w-4 h-4 transform rounded-full bg-muted-foreground shadow transition duration-200 ease-in-out",
                  syncEnabled ? "translate-x-6 bg-white" : "translate-x-0"
                )}
              />
            </button>
          </div>
          
          <div className="flex gap-3 pt-2">
            <Button onClick={onConnect} disabled={saving || !email || !password} data-testid="garmin-connect">
              {saving ? "Updating..." : "Update"}
            </Button>
            <SyncButton onSync={triggerGarminSync} label="Sync Now" />
            <Button
              variant="destructive"
              onClick={onDisconnect}
              disabled={saving}
              data-testid="garmin-disconnect"
            >
              Disconnect
            </Button>
          </div>
        </>
      ) : (
        <Button
          onClick={onConnect}
          disabled={saving || !email || !password}
          data-testid="garmin-connect"
        >
          {saving ? "Connecting..." : "Connect"}
        </Button>
      )}
    </div>
  );
}
