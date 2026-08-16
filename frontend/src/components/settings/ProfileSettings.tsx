import { useState, useRef } from "react";
import type { User } from "@/api";
import { updatePreferences, uploadAvatar, deleteAvatar, ApiError } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { FeedbackAlert } from "./FeedbackAlert";

interface ProfileSettingsProps {
  user: User;
  onUserUpdate: (user: User) => void;
}

export function ProfileSettings({ user, onUserUpdate }: ProfileSettingsProps) {
  const [displayName, setDisplayName] = useState(user.display_name || "");
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const originalDisplayName = useRef(user.display_name || "");

  async function handleDisplayNameBlur() {
    const trimmedName = displayName.trim();
    if (trimmedName === originalDisplayName.current) return;
    
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ 
        display_name: trimmedName || null,
      });
      onUserUpdate(updated);
      originalDisplayName.current = trimmedName;
      setFeedback({ type: "success", message: "Profile saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save profile";
      setFeedback({ type: "error", message });
      setDisplayName(originalDisplayName.current);
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
        <div className="flex items-start gap-8">
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
          </div>


          {/* Form fields */}
          <div className="flex-1 space-y-5 max-w-xl">
            <div className="space-y-1.5">
              <Label className="text-muted-foreground text-sm font-medium">Email</Label>
              <Input
                type="email"
                value={user.email}
                disabled
                className="h-11 px-4 text-base md:text-base bg-muted text-muted-foreground"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-muted-foreground text-sm font-medium">Display Name</Label>
              <Input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                onBlur={handleDisplayNameBlur}
                placeholder="How you want to be called"
                disabled={saving}
                className="h-11 px-4 text-base md:text-base bg-muted"
              />
              <p className="text-xs text-muted-foreground mt-1.5">
                This name will be shown in the header and anywhere your profile appears
              </p>
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingAvatar}
                className="bg-muted hover:bg-muted/80 border border-border"
              >
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  </svg>
                  Change photo
                </div>
              </Button>
              {user.avatar_path && (
                <Button
                  variant="ghost"
                  onClick={handleDeleteAvatar}
                  disabled={uploadingAvatar}
                  className="text-destructive hover:text-destructive/80 hover:border-destructive/20 border border-transparent"
                >
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Remove
                  </div>
                </Button>
              )}
            </div>
          </div>
        </div>

        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}
