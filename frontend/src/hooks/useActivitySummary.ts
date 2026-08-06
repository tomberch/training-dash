import { useState, useEffect, useCallback } from "react";
import type { Activity } from "../api";
import {
  ApiError,
  fetchActivity,
  updateActivityTitle,
  generateActivityTitle,
} from "../api";

export interface UseActivitySummaryResult {
  // Loading/error state
  loading: boolean;
  error: Error | ApiError | null;
  setError: (error: Error | ApiError | null) => void;

  // Core data
  activity: Activity | null;
  setActivity: (activity: Activity | null) => void;

  // Title editing
  isEditingTitle: boolean;
  setIsEditingTitle: (editing: boolean) => void;
  editedTitle: string;
  setEditedTitle: (title: string) => void;
  saveTitle: (title: string) => Promise<void>;

  // Title generation
  isGeneratingTitle: boolean;
  generateTitle: () => Promise<void>;
}

/**
 * Hook for activity summary/metadata - always loaded eagerly.
 * Handles: basic activity data, title editing, title generation
 */
export function useActivitySummary(activityId: string): UseActivitySummaryResult {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  // Title editing state
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState("");
  const [isGeneratingTitle, setIsGeneratingTitle] = useState(false);

  // Fetch activity on mount/id change
  useEffect(() => {
    setLoading(true);
    setError(null);

    fetchActivity(activityId)
      .then((a) => setActivity(a))
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, [activityId]);

  const saveTitle = useCallback(
    async (title: string) => {
      const updated = await updateActivityTitle(activityId, title);
      setActivity((prev) =>
        prev ? { ...prev, title: updated.title, title_source: updated.title_source } : prev
      );
      setIsEditingTitle(false);
    },
    [activityId]
  );

  const generateTitle = useCallback(async () => {
    setIsGeneratingTitle(true);
    try {
      const updated = await generateActivityTitle(activityId);
      setActivity((prev) =>
        prev ? { ...prev, title: updated.title, title_source: updated.title_source } : prev
      );
    } finally {
      setIsGeneratingTitle(false);
    }
  }, [activityId]);

  return {
    loading,
    error,
    setError,
    activity,
    setActivity,
    isEditingTitle,
    setIsEditingTitle,
    editedTitle,
    setEditedTitle,
    saveTitle,
    isGeneratingTitle,
    generateTitle,
  };
}
