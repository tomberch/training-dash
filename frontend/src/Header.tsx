import { useState, useRef, useEffect } from "react";
import { logout, uploadFit, fetchJobStatus } from "./api";

interface HeaderProps {
  displayName: string | null;
  email: string;
  avatarPath: string | null;
  onLogout: () => void;
  onSettings: () => void;
  onUploadComplete?: () => void;
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

/** Generate a consistent color based on email - harmonious with indigo UI */
function getAvatarColor(email: string): string {
  // Limited to blue/indigo/violet/purple tones to harmonize with primary indigo UI
  const colors = [
    "bg-blue-500", "bg-indigo-500", "bg-violet-500", "bg-purple-500",
    "bg-sky-500", "bg-indigo-600", "bg-violet-600", "bg-purple-600",
  ];
  let hash = 0;
  for (let i = 0; i < email.length; i++) {
    hash = email.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function Header({ 
  displayName, 
  email, 
  avatarPath, 
  onLogout, 
  onSettings, 
  onUploadComplete, 
  showUpload = true 
}: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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
      if ("job_id" in result && result.job_id) {
        setProcessing(true);
        const jobId = result.job_id;
        const maxPolls = 30;
        for (let i = 0; i < maxPolls; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          try {
            const status = await fetchJobStatus(jobId);
            if (status.status === "complete" || status.status === "not_found") {
              break;
            }
          } catch {
            // Error checking status, keep polling
          }
        }
        setProcessing(false);
      }
      onUploadComplete?.();
    } catch (err) {
      console.error("Upload failed:", err);
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
  const avatarColorClass = getAvatarColor(email);

  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">TrainDash</h1>
        
        <div className="flex items-center gap-4">
          {showUpload && (
            <label className="relative cursor-pointer">
              <input
                type="file"
                accept=".fit"
                onChange={handleUpload}
                disabled={uploading || processing}
                className="sr-only"
              />
              <span
                className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  uploading || processing
                    ? "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed"
                    : "bg-indigo-600 text-white hover:bg-indigo-700"
                }`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                {uploading ? "Uploading..." : processing ? "Processing..." : "Upload FIT"}
              </span>
            </label>
          )}
          
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              data-testid="user-menu-button"
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              {/* Round Avatar */}
              {avatarPath ? (
                <img
                  src={avatarPath}
                  alt="Avatar"
                  className="w-9 h-9 rounded-full object-cover border-2 border-gray-200 dark:border-gray-600"
                />
              ) : (
                <div 
                  className={`w-9 h-9 rounded-full flex items-center justify-center text-white font-medium text-sm ${avatarColorClass}`}
                >
                  {initials}
                </div>
              )}
              <svg
                className={`w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform ${menuOpen ? "rotate-180" : ""}`}
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
                className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50"
              >
                {/* User info header */}
                <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                    {displayName || email.split("@")[0]}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {email}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onSettings();
                  }}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Settings
                </button>
                <button
                  onClick={handleLogout}
                  data-testid="logout-button"
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
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
