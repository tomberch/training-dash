import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { logout, uploadFit, fetchJobStatus } from "./api";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { useTheme } from "./hooks/useTheme";
import { SunIcon, MoonIcon } from "./components/icons/ThemeIcons";

interface HeaderProps {
  displayName: string | null;
  email: string;
  avatarPath: string | null;
  onLogout: () => void;
  onSettings: () => void;
  onUploadComplete?: () => void;
  onUploadTriggerRef?: (trigger: () => void) => void;
  showUpload?: boolean;
}

/** Get initials from display name or email */
function getInitials(displayName: string | null, email: string): string {
  if (displayName) {
    const parts = displayName.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  }
  // Fallback to email: take first letter, and first letter after @ or .
  const local = email.split("@")[0];
  if (local.includes(".")) {
    const parts = local.split(".");
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return local.slice(0, 2).toUpperCase();
}

/** Generate a consistent hue based on email for avatar background */
function getAvatarHue(email: string): number {
  let hash = 0;
  for (let i = 0; i < email.length; i++) {
    hash = email.charCodeAt(i) + ((hash << 5) - hash);
  }
  // Return a hue in the blue-purple range (200-300) to harmonize with primary
  return 200 + (Math.abs(hash) % 100);
}

export function Header({ 
  displayName, 
  email, 
  avatarPath, 
  onLogout, 
  onSettings, 
  onUploadComplete,
  onUploadTriggerRef,
  showUpload = true 
}: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { resolvedTheme, setTheme } = useTheme();
  const navigate = useNavigate();

  // Expose the upload trigger function to parent
  useEffect(() => {
    if (onUploadTriggerRef) {
      onUploadTriggerRef(() => fileInputRef.current?.click());
    }
  }, [onUploadTriggerRef]);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [menuOpen]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadFit(file);
      let activityId: string | null | undefined;
      
      if ("job_id" in result && result.job_id) {
        setProcessing(true);
        const jobId = result.job_id;
        const maxPolls = 30;
        for (let i = 0; i < maxPolls; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          try {
            const status = await fetchJobStatus(jobId);
            if (status.status === "complete") {
              activityId = status.result?.activity_id;
              break;
            }
            if (status.status === "not_found") {
              break;
            }
          } catch {
            // Error checking status, keep polling
          }
        }
        setProcessing(false);
      } else if ("activity_id" in result) {
        activityId = result.activity_id as string;
      }
      
      onUploadComplete?.();
      
      // Show success toast with action to view activity
      if (activityId) {
        toast.success("Activity uploaded successfully", {
          action: {
            label: "View",
            onClick: () => navigate(`/activities/${activityId}`),
          },
        });
      } else {
        toast.success("Activity uploaded successfully");
      }
    } catch (err) {
      console.error("Upload failed:", err);
      toast.error("Upload failed", {
        description: err instanceof Error ? err.message : "Please try again",
      });
    } finally {
      setUploading(false);
      // Reset the input so the same file can be uploaded again
      e.target.value = "";
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Even if logout fails, clear local state
    }
    onLogout();
  }

  const initials = getInitials(displayName, email);
  const avatarHue = getAvatarHue(email);

  return (
    <header className="bg-card border-b border-border">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">TrainDash</h1>
        
        <div className="flex items-center gap-4">
          {showUpload && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".fit"
                onChange={handleUpload}
                disabled={uploading || processing}
                className="sr-only"
              />
              <Button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || processing}
                className="gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                {uploading ? "Uploading..." : processing ? "Processing..." : "Upload FIT"}
              </Button>
            </>
          )}
          
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              data-testid="user-menu-button"
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              <Avatar>
                {avatarPath ? (
                  <AvatarImage src={avatarPath} alt="Avatar" />
                ) : null}
                <AvatarFallback 
                  style={{ 
                    backgroundColor: `hsl(${avatarHue}, 60%, 50%)`,
                    color: 'white'
                  }}
                >
                  {initials}
                </AvatarFallback>
              </Avatar>
              <svg
                className={cn(
                  "w-4 h-4 text-muted-foreground transition-transform",
                  menuOpen && "rotate-180"
                )}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            
            {menuOpen && (
              <div
                data-testid="user-menu-dropdown"
                className="absolute right-0 mt-2 w-56 bg-popover rounded-lg shadow-lg border border-border py-1 z-50"
              >
                {/* User info header */}
                <div className="px-4 py-3 border-b border-border">
                  <p className="text-sm font-medium text-foreground truncate">
                    {displayName || email.split("@")[0]}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {email}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onSettings();
                  }}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Settings
                </button>
                <button
                  onClick={() => setTheme(resolvedTheme === "latte" ? "mocha" : "latte")}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                >
                  {resolvedTheme === "latte" ? (
                    <MoonIcon className="w-4 h-4" />
                  ) : (
                    <SunIcon className="w-4 h-4" />
                  )}
                  {resolvedTheme === "latte" ? "Dark mode" : "Light mode"}
                </button>
                <button
                  onClick={handleLogout}
                  data-testid="logout-button"
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
