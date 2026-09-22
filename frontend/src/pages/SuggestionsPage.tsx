/**
 * Segment Suggestions Page
 *
 * Pending climb/sprint suggestions detected from the user's rides. Card grid
 * (UX #480 List Variant 1), approve-with-naming modal, single and bulk dismiss.
 */

import { useEffect, useState } from "react";
import type { JSX } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useDecrementPendingSuggestions } from "@/contexts/UserContext";
import {
  dismissAllSuggestions,
  dismissSuggestion,
  fetchSuggestions,
} from "@/api/suggestions";
import type { SegmentSuggestion } from "@/api/suggestions";
import {
  ClimbCategoryBadge,
  SegmentTypeIcon,
} from "@/components/segments/SegmentBadges";
import { ElevationProfile } from "@/components/segments/ElevationProfile";
import { SegmentMiniMap } from "@/components/segments/SegmentMiniMap";
import { SegmentNamingDialog } from "@/components/segments/SegmentNamingDialog";
import {
  formatDistance,
  formatElevation,
  formatDistanceAxis,
  type UnitSystem,
} from "@/format";

const PER_PAGE = 20;

// =============================================================================
// Suggestion card
// =============================================================================

function SuggestionCard({
  suggestion,
  unitSystem,
  onApprove,
  onDismiss,
}: {
  suggestion: SegmentSuggestion;
  unitSystem: UnitSystem;
  onApprove: (suggestion: SegmentSuggestion) => void;
  onDismiss: (id: string) => void;
}): JSX.Element {
  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-3">
        {/* Header: type, category, repetitions */}
        <div className="flex items-center gap-2">
          <SegmentTypeIcon type={suggestion.segment_type} />
          <span className="font-medium">Detected Climb</span>
          <ClimbCategoryBadge category={suggestion.climb_category} />
          <span className="text-caption ml-auto">{suggestion.repetition_count}× ridden</span>
        </div>

        {/* Map left, profile + stats right */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div className="md:col-span-2">
            <SegmentMiniMap polyline={suggestion.polyline} height={256} />
          </div>
          <div className="md:col-span-3 space-y-2">
            <ElevationProfile
              profile={suggestion.elevation_profile}
              height={112}
              formatDistanceLabel={formatDistanceAxis}
            />
            <div className="text-body-secondary">
              {formatDistance(suggestion.distance_m, unitSystem)} ·{" "}
              {formatElevation(suggestion.elevation_gain_m, unitSystem)} ·{" "}
              {suggestion.avg_grade_pct.toFixed(1)}% avg ·{" "}
              {suggestion.max_grade_pct.toFixed(1)}% max
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button size="sm" onClick={() => onApprove(suggestion)}>
            Save
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onDismiss(suggestion.id)}>
            Dismiss
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function SuggestionCardSkeleton(): JSX.Element {
  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-3">
        <Skeleton className="h-5 w-40" />
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div className="md:col-span-2 min-h-[256px] bg-muted" />
          <div className="md:col-span-3 space-y-2">
            <Skeleton className="h-[112px] w-full" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Page
// =============================================================================

interface SuggestionsPageProps {
  unitSystem: UnitSystem;
}

export function SuggestionsPage({ unitSystem }: SuggestionsPageProps): JSX.Element {
  const decrementPendingSuggestions = useDecrementPendingSuggestions();
  const [items, setItems] = useState<SegmentSuggestion[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [namingTarget, setNamingTarget] = useState<SegmentSuggestion | null>(null);
  const [dismissAllOpen, setDismissAllOpen] = useState(false);

  const load = (): void => {
    setIsLoading(true);
    setError(null);
    fetchSuggestions(page, PER_PAGE)
      .then((data) => {
        setItems(data.items);
        setTotal(data.meta.total);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const handleDismiss = async (id: string): Promise<void> => {
    try {
      await dismissSuggestion(id);
      decrementPendingSuggestions(1);
      load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to dismiss suggestion";
      setError(message);
    }
  };

  const handleDismissAll = async (): Promise<void> => {
    try {
      await dismissAllSuggestions();
      decrementPendingSuggestions(total);
      setDismissAllOpen(false);
      setPage(1);
      load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to dismiss suggestions";
      setError(message);
    }
  };

  const handleCreated = (_segmentId: string): void => {
    decrementPendingSuggestions(1);
    setNamingTarget(null);
    setPage(1);
    load();
  };

  const isEmpty = !isLoading && !error && items.length === 0;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-page-title">Segment Suggestions</h1>
          <p className="text-body-secondary mt-2">Climbs detected on your rides</p>
        </div>
        {items.length > 0 && (
          <AlertDialog open={dismissAllOpen} onOpenChange={setDismissAllOpen}>
            <AlertDialogTrigger asChild>
              <Button variant="ghost">Dismiss All</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Dismiss all suggestions?</AlertDialogTitle>
                <AlertDialogDescription>
                  This removes all {total} pending suggestion{total === 1 ? "" : "s"}. This
                  cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction variant="destructive" onClick={handleDismissAll}>
                  Dismiss All
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 gap-4">
          {Array.from({ length: 4 }, (_, i) => (
            <SuggestionCardSkeleton key={i} />
          ))}
        </div>
      )}

      {isEmpty && (
        <EmptyState
          title="No suggestions — keep riding!"
          description="Climb and sprint segments are suggested after you've ridden them repeatedly."
        />
      )}

      {!isLoading && !error && items.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-4">
            {items.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                unitSystem={unitSystem}
                onApprove={setNamingTarget}
                onDismiss={handleDismiss}
              />
            ))}
          </div>

          {total > PER_PAGE && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-body-secondary">
                Page {page} of {Math.ceil(total / PER_PAGE)} · {total} suggestions
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= Math.ceil(total / PER_PAGE)}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      <SegmentNamingDialog
        suggestion={namingTarget}
        open={namingTarget !== null}
        onOpenChange={(open) => !open && setNamingTarget(null)}
        onCreated={handleCreated}
        unitSystem={unitSystem}
      />
    </div>
  );
}
