/**
 * Notification helpers - show toast AND persist to bell dropdown
 */
import { toast } from "sonner";
import { createNotification } from "@/api";

type NotifyType = "success" | "error" | "info";

interface NotifyOptions {
  /** Description shown below the main message in the toast */
  description?: string;
  /** Notification type for the bell (defaults to toast type) */
  bellType?: string;
  /** Skip persisting to bell (toast only) */
  toastOnly?: boolean;
}

/**
 * Show a toast notification AND persist it to the bell dropdown.
 * Use for important events the user might want to review later.
 * 
 * @param type - "success" | "error" | "info"
 * @param message - Main notification message
 * @param options - Additional options
 */
export async function notify(
  type: NotifyType,
  message: string,
  options: NotifyOptions = {}
): Promise<void> {
  const { description, bellType, toastOnly = false } = options;

  // Show toast immediately
  const toastOptions = description ? { description } : undefined;
  switch (type) {
    case "success":
      toast.success(message, toastOptions);
      break;
    case "error":
      toast.error(message, toastOptions);
      break;
    case "info":
    default:
      toast(message, toastOptions);
      break;
  }

  // Persist to bell (fire-and-forget, don't block on it)
  if (!toastOnly) {
    const notificationType = bellType || `frontend_${type}`;
    // Include description in the persisted message if present
    const fullMessage = description ? `${message}: ${description}` : message;
    
    createNotification(notificationType, fullMessage).catch((err) => {
      // Log but don't fail - toast already shown
      console.warn("Failed to persist notification to bell:", err);
    });
  }
}

/**
 * Success notification - shown in toast and persisted to bell
 */
export function notifySuccess(message: string, options?: Omit<NotifyOptions, "bellType"> & { bellType?: string }): void {
  notify("success", message, options);
}

/**
 * Error notification - shown in toast and persisted to bell
 */
export function notifyError(message: string, options?: Omit<NotifyOptions, "bellType"> & { bellType?: string }): void {
  notify("error", message, options);
}

/**
 * Info notification - shown in toast and persisted to bell
 */
export function notifyInfo(message: string, options?: Omit<NotifyOptions, "bellType"> & { bellType?: string }): void {
  notify("info", message, options);
}
