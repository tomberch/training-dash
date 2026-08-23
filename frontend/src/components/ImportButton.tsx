import type { JSX } from "react";
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  fetchMyXertCredentials,
  fetchMyGarminCredentials,
  triggerXertImport,
  triggerGarminImport,
} from "../api";
import { Button } from "@/components/ui/button";
import { notifyError } from "@/lib/notify";

interface ImportButtonProps {
  className?: string;
  onImportComplete?: () => void;
}

// Custom event name for import settings changes
export const IMPORT_SETTINGS_CHANGED_EVENT = "import-settings-changed";

/**
 * Dispatch this event when import settings change to update the header ImportButton.
 */
export function notifyImportSettingsChanged(): void {
  window.dispatchEvent(new CustomEvent(IMPORT_SETTINGS_CHANGED_EVENT));
}

/**
 * Import button that triggers import for all configured integrations with import enabled.
 * Only renders if at least one integration (Xert or Garmin) has import enabled.
 */
export function ImportButton({ className, onImportComplete }: ImportButtonProps): JSX.Element | null {
  const [importing, setImporting] = useState(false);
  const [xertImportEnabled, setXertImportEnabled] = useState(false);
  const [garminImportEnabled, setGarminImportEnabled] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const checkIntegrations = useCallback(async () => {
    try {
      const [xertStatus, garminStatus] = await Promise.all([
        fetchMyXertCredentials(),
        fetchMyGarminCredentials(),
      ]);
      // Only consider integrations that are both configured AND have import enabled
      setXertImportEnabled(xertStatus.configured && xertStatus.sync_enabled === true);
      setGarminImportEnabled(garminStatus.configured && garminStatus.sync_enabled === true);
    } catch (err) {
      console.error("Failed to check integration status:", err);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    checkIntegrations();
  }, [checkIntegrations]);

  // Re-check integrations when window gains focus (user may have changed settings)
  useEffect(() => {
    const handleFocus = () => checkIntegrations();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [checkIntegrations]);

  // Re-check when import settings change (from settings page)
  useEffect(() => {
    const handleSettingsChanged = () => checkIntegrations();
    window.addEventListener(IMPORT_SETTINGS_CHANGED_EVENT, handleSettingsChanged);
    return () => window.removeEventListener(IMPORT_SETTINGS_CHANGED_EVENT, handleSettingsChanged);
  }, [checkIntegrations]);

  const hasAnyImportEnabled = xertImportEnabled || garminImportEnabled;

  async function handleImport(): Promise<void> {
    setImporting(true);
    try {
      const importPromises: Promise<{ success: boolean; job_id?: string }>[] = [];

      if (xertImportEnabled) {
        importPromises.push(triggerXertImport());
      }
      if (garminImportEnabled) {
        importPromises.push(triggerGarminImport());
      }

      await Promise.all(importPromises);

      toast.success("Import started", {
        description: "Your activities will be imported in the background.",
      });

      onImportComplete?.();
    } catch (err) {
      console.error("Import failed:", err);
      notifyError("Import failed", {
        description: err instanceof Error ? err.message : "Please try again",
        bellType: "import_failed",
      });
    } finally {
      setImporting(false);
    }
  }

  // Don't render anything until we've checked integration status
  if (!loaded) {
    return null;
  }

  // Don't render if no integrations have import enabled
  if (!hasAnyImportEnabled) {
    return null;
  }

  return (
    <Button
      variant="outline"
      onClick={handleImport}
      disabled={importing}
      className={className}
      data-testid="import-button"
    >
      {importing ? (
        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
          />
        </svg>
      )}
      {importing ? "Importing..." : "Import"}
    </Button>
  );
}
