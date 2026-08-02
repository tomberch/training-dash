import { useState, useRef, useEffect } from "react";
import { logout, uploadFit, fetchJobStatus } from "./api";

interface HeaderProps {
  username: string;
  onLogout: () => void;
  onSettings: () => void;
  onUploadComplete?: () => void;
  showUpload?: boolean;
}

export function Header({ username, onLogout, onSettings, onUploadComplete, showUpload = true }: HeaderProps) {
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

  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">TrainingDash</h1>
        
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
                className={`inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  uploading || processing
                    ? "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed"
                    : "bg-indigo-600 text-white hover:bg-indigo-700"
                }`}
              >
                {uploading ? "Uploading..." : processing ? "Processing..." : "Upload FIT"}
              </span>
            </label>
          )}
          
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              data-testid="user-menu-button"
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              <span>{username}</span>
              <svg
                className={`w-4 h-4 transition-transform ${menuOpen ? "rotate-180" : ""}`}
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
                className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50"
              >
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onSettings();
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  Settings
                </button>
                <button
                  onClick={handleLogout}
                  data-testid="logout-button"
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
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
