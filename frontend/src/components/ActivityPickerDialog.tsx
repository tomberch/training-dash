/**
 * Activity Picker Dialog
 * 
 * Dialog for selecting activities to link to an event.
 * Shows activities within the event's date range with pagination.
 */

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { fetchAvailableActivities, batchLinkActivities } from "@/api/events";
import type { AvailableActivity, PaginatedActivities } from "@/api/events";
import { toast } from "sonner";

interface ActivityPickerDialogProps {
  eventId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onLinked?: () => void;
}

function formatDate(dateString: string | null) {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function formatDuration(seconds: number | null) {
  if (!seconds) return "—";
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

export function ActivityPickerDialog({
  eventId,
  open,
  onOpenChange,
  onLinked,
}: ActivityPickerDialogProps) {
  const [data, setData] = useState<PaginatedActivities | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isLinking, setIsLinking] = useState(false);
  const perPage = 10;

  // Load activities when dialog opens
  useEffect(() => {
    if (!open) {
      setSelectedIds(new Set());
      setPage(1);
      return;
    }

    setIsLoading(true);
    setError(null);
    fetchAvailableActivities(eventId, page, perPage)
      .then((result) => {
        setData(result);
        // Pre-select already linked activities
        const linked = new Set(
          result.activities.filter((a) => a.is_linked).map((a) => a.id)
        );
        setSelectedIds(linked);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [eventId, open, page, perPage]);

  const toggleActivity = (id: string, isLinked: boolean) => {
    // Don't allow unlinking already linked activities from this dialog
    if (isLinked) return;
    
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleLink = async () => {
    // Get newly selected (not already linked)
    const toLink = Array.from(selectedIds).filter((id) => {
      const activity = data?.activities.find((a) => a.id === id);
      return activity && !activity.is_linked;
    });

    if (toLink.length === 0) {
      onOpenChange(false);
      return;
    }

    setIsLinking(true);
    try {
      await batchLinkActivities(eventId, toLink);
      toast.success(`Linked ${toLink.length} ${toLink.length === 1 ? "activity" : "activities"}`);
      onOpenChange(false);
      onLinked?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to link activities");
    } finally {
      setIsLinking(false);
    }
  };

  const activities = data?.activities || [];
  const pagination = data?.pagination;
  const newlySelectedCount = Array.from(selectedIds).filter((id) => {
    const activity = activities.find((a) => a.id === id);
    return activity && !activity.is_linked;
  }).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Link Activities</DialogTitle>
          <DialogDescription>
            Select activities from the event's date range to link.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[400px] overflow-y-auto -mx-6 px-6">
          {error && (
            <div className="bg-destructive/10 text-destructive p-3 rounded-lg text-sm mb-4">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                  <Skeleton className="w-5 h-5 rounded" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : activities.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No activities found in this event's date range.</p>
              <p className="text-sm mt-2">Upload activities that fall between the event's start and end dates.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {activities.map((activity: AvailableActivity) => (
                <label
                  key={activity.id}
                  className={cn(
                    "flex items-center gap-3 p-3 rounded-lg transition-colors cursor-pointer",
                    activity.is_linked
                      ? "bg-primary/10 border border-primary/20"
                      : selectedIds.has(activity.id)
                      ? "bg-muted border border-primary/50"
                      : "bg-muted/50 hover:bg-muted border border-transparent"
                  )}
                >
                  <Checkbox
                    checked={selectedIds.has(activity.id)}
                    onCheckedChange={() => toggleActivity(activity.id, activity.is_linked)}
                    disabled={activity.is_linked}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">
                      {activity.title || "Untitled Activity"}
                    </div>
                    <div className="text-caption flex gap-3">
                      <span>{formatDate(activity.started_at)}</span>
                      {activity.distance_km && <span>{activity.distance_km.toFixed(1)} km</span>}
                      {activity.duration_seconds && <span>{formatDuration(activity.duration_seconds)}</span>}
                    </div>
                  </div>
                  {activity.is_linked && (
                    <span className="text-xs text-primary font-medium">Linked</span>
                  )}
                </label>
              ))}
            </div>
          )}

          {/* Pagination */}
          {pagination && pagination.total_pages > 1 && (
            <div className="flex justify-center gap-2 pt-4 mt-4 border-t border-border">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1 || isLoading}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span className="flex items-center px-3 text-sm text-muted-foreground">
                {page} / {pagination.total_pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= pagination.total_pages || isLoading}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLinking}>
            Cancel
          </Button>
          <Button onClick={handleLink} disabled={isLinking || newlySelectedCount === 0}>
            {isLinking
              ? "Linking..."
              : newlySelectedCount > 0
              ? `Link ${newlySelectedCount} ${newlySelectedCount === 1 ? "Activity" : "Activities"}`
              : "Link Activities"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
