import type { JSX } from "react";
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  fetchMyXertCredentials,
  fetchMyGarminCredentials,
  triggerXertSync,
  triggerGarminSync,
} from "../api";
import { Button } from "@/components/ui/button";

interface SyncButtonProps {
  className?: string;
  onSyncComplete?: () => void;
}

/**
 * Sync button that triggers sync for all configured integrations.
 * Only renders if at least one integration (Xert or Garmin) is configured.
 */
export function SyncButton({ className, onSyncComplete }: SyncButtonProps): JSX.Element | null {
  const [syncing, setSyncing] = useState(false);
  const [hasXert, setHasXert] = useState(false);
  const [hasGarmin, setHasGarmin] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const checkIntegrations = useCallback(async () => {
    try {
      const [xertStatus, garminStatus] = await Promise.all([
        fetchMyXertCredentials(),
        fetchMyGarminCredentials(),
      ]);
      setHasXert(xertStatus.configured);
      setHasGarmin(garminStatus.configured);
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

  const hasAnyIntegration = hasXert || hasGarmin;

  async function handleSync(): Promise<void> {
    setSyncing(true);
    try {
      const syncPromises: Promise<{ success: boolean; job_id?: string }>[] = [];

      if (hasXert) {
        syncPromises.push(triggerXertSync());
      }
      if (hasGarmin) {
        syncPromises.push(triggerGarminSync());
      }

      await Promise.all(syncPromises);

      toast.success("Sync started", {
        description: "Your activities will be synced in the background.",
      });

      onSyncComplete?.();
    } catch (err) {
      console.error("Sync failed:", err);
      toast.error("Sync failed", {
        description: err instanceof Error ? err.message : "Please try again",
      });
    } finally {
      setSyncing(false);
    }
  }

  // Don't render anything until we've checked integration status
  if (!loaded) {
    return null;
  }

  // Don't render if no integrations are configured
  if (!hasAnyIntegration) {
    return null;
  }

  return (
    <Button
      variant="outline"
      onClick={handleSync}
      disabled={syncing}
      className={className}
      data-testid="sync-button"
    >
      {syncing ? (
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
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      )}
      {syncing ? "Syncing..." : "Sync"}
    </Button>
  );
}
