import type { JSX } from "react";
import { useState, useRef, useEffect } from "react";
import { logout } from "../api";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { useTheme } from "../hooks/useTheme";
import { SunIcon, MoonIcon } from "./icons/ThemeIcons";

interface UserMenuProps {
  displayName: string | null;
  email: string;
  avatarPath: string | null;
  onLogout: () => void;
  onSettings: () => void;
  /** Whether to show the chevron indicator (default: true for header, false for inline) */
  showChevron?: boolean;
  /** Size of the avatar (default: "default") */
  size?: "default" | "lg";
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
  return 200 + (Math.abs(hash) % 100);
}

/**
 * Reusable user avatar with dropdown menu for settings, theme toggle, and logout.
 * Used in Header and Dashboard.
 */
export function UserMenu({
  displayName,
  email,
  avatarPath,
  onLogout,
  onSettings,
  showChevron = true,
  size = "default",
}: UserMenuProps): JSX.Element {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { resolvedTheme, setTheme } = useTheme();

  const initials = getInitials(displayName, email);
  const avatarHue = getAvatarHue(email);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent): void {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [menuOpen]);

  async function handleLogout(): Promise<void> {
    try {
      await logout();
    } catch {
      // Even if logout fails, clear local state
    }
    onLogout();
  }

  function cycleTheme(): void {
    const themes = ["latte", "mocha", "midnight"] as const;
    const current = themes.indexOf(resolvedTheme as (typeof themes)[number]);
    const next = themes[(current + 1) % themes.length];
    setTheme(next);
  }

  const avatarSizeClass = size === "lg" ? "h-10 w-10" : "h-8 w-8";

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setMenuOpen(!menuOpen)}
        data-testid="user-menu-button"
        className={cn(
          "flex items-center gap-2 hover:opacity-80 transition-opacity",
          "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background rounded-full"
        )}
      >
        <Avatar className={avatarSizeClass}>
          {avatarPath ? <AvatarImage src={avatarPath} alt="Avatar" /> : null}
          <AvatarFallback
            style={{
              backgroundColor: `hsl(${avatarHue}, 60%, 50%)`,
              color: "white",
            }}
            className="font-semibold"
          >
            {initials}
          </AvatarFallback>
        </Avatar>
        {showChevron && (
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
        )}
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
            <p className="text-caption truncate">{email}</p>
          </div>

          {/* Theme toggle */}
          <button
            onClick={cycleTheme}
            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
          >
            {resolvedTheme === "latte" ? (
              <SunIcon className="w-4 h-4" />
            ) : (
              <MoonIcon className="w-4 h-4" />
            )}
            <span className="capitalize">{resolvedTheme} theme</span>
          </button>

          {/* Settings */}
          <button
            onClick={() => {
              setMenuOpen(false);
              onSettings();
            }}
            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            Settings
          </button>

          <div className="border-t border-border my-1" />

          {/* Logout */}
          <button
            onClick={handleLogout}
            data-testid="logout-button"
            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-destructive hover:bg-muted transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
