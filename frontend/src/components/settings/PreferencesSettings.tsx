import { useState } from "react";
import type { User } from "@/api";
import { updatePreferences, ApiError } from "@/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useTheme } from "@/hooks/useTheme";
import type { Theme } from "@/hooks/useTheme";
import { SunIcon, MoonIcon, MonitorIcon, SparklesIcon } from "@/components/icons/ThemeIcons";
import { FeedbackAlert } from "./FeedbackAlert";

interface PreferencesSettingsProps {
  user: User;
  onUserUpdate: (user: User) => void;
}

export function PreferencesSettings({ user, onUserUpdate }: PreferencesSettingsProps) {
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
          Display
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Theme selector */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-foreground mb-1">Theme</h3>
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
            <h3 className="font-medium text-foreground mb-1">Unit System</h3>
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
