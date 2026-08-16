import type { JSX } from "react";
import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import {
  fetchNotifications,
  acceptNotification,
  dismissNotification,
  dismissAllNotifications,
  type Notification,
} from "../api";

interface NotificationBellProps {
  /** Polling interval in ms (default: 60000 = 1 minute) */
  pollInterval?: number;
}

/**
 * Bell icon with dropdown showing pending notifications.
 * Displays unread count badge and allows dismissing or accepting notifications.
 */
export function NotificationBell({ pollInterval = 60000 }: NotificationBellProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [totalPending, setTotalPending] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const loadNotifications = useCallback(async () => {
    try {
      const response = await fetchNotifications(20);
      setNotifications(response.notifications);
      setTotalPending(response.total_pending);
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
    }
  }, []);

  // Initial load and polling
  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, pollInterval);
    return () => clearInterval(interval);
  }, [loadNotifications, pollInterval]);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent): void {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  async function handleAccept(notification: Notification): Promise<void> {
    setIsLoading(true);
    try {
      await acceptNotification(notification.id);
      await loadNotifications();
    } catch (error) {
      console.error("Failed to accept notification:", error);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDismiss(id: number): Promise<void> {
    setIsLoading(true);
    try {
      await dismissNotification(id);
      await loadNotifications();
    } catch (error) {
      console.error("Failed to dismiss notification:", error);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDismissAll(): Promise<void> {
    setIsLoading(true);
    try {
      await dismissAllNotifications();
      await loadNotifications();
    } catch (error) {
      console.error("Failed to dismiss all notifications:", error);
    } finally {
      setIsLoading(false);
    }
  }

  function formatTime(isoString: string): string {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  }

  function isActionable(notification: Notification): boolean {
    return notification.type === "ftp_suggestion" || notification.type === "hrmax_suggestion";
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "relative p-2 rounded-full hover:bg-muted transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
        )}
        aria-label={`Notifications${totalPending > 0 ? ` (${totalPending} pending)` : ""}`}
      >
        {/* Bell icon */}
        <svg
          className="w-5 h-5 text-muted-foreground"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* Badge */}
        {totalPending > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-xs font-medium text-white bg-destructive rounded-full">
            {totalPending > 99 ? "99+" : totalPending}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-popover rounded-lg shadow-lg border border-border z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <h3 className="text-sm font-medium text-foreground">Notifications</h3>
            {notifications.length > 0 && (
              <button
                onClick={handleDismissAll}
                disabled={isLoading}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
              >
                Dismiss all
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-muted-foreground text-sm">
                No notifications
              </div>
            ) : (
              notifications.map((notification) => (
                <div
                  key={notification.id}
                  className="px-4 py-3 border-b border-border last:border-b-0 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground">{notification.message}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {formatTime(notification.created_at)}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDismiss(notification.id)}
                      disabled={isLoading}
                      className="p-1 text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                      aria-label="Dismiss"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>

                  {/* Action button for actionable notifications */}
                  {isActionable(notification) && notification.payload && (
                    <button
                      onClick={() => handleAccept(notification)}
                      disabled={isLoading}
                      className="mt-2 px-3 py-1 text-xs font-medium text-primary-foreground bg-primary rounded hover:bg-primary/90 transition-colors disabled:opacity-50"
                    >
                      {notification.type === "ftp_suggestion" && notification.payload.suggested_ftp
                        ? `Apply ${notification.payload.suggested_ftp}W FTP`
                        : notification.type === "hrmax_suggestion" && notification.payload.suggested_hrmax
                          ? `Apply ${notification.payload.suggested_hrmax} HRmax`
                          : "Apply"}
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
