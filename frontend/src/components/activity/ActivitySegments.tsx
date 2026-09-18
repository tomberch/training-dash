/**
 * Activity segments card and inline suggestion card.
 *
 * Shown on the activity detail page: a list of segment efforts crossed
 * during the ride, plus (when present) an inline card to approve/dismiss the
 * pending suggestion whose climb was auto-detected from this activity.
 */

import { useState } from "react";
import type { JSX } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { ActivitySegmentEffort, ActivitySegments } from "@/api/segments";
import type { SegmentSuggestion } from "@/api/suggestions";
import { dismissSuggestion } from "@/api/suggestions";
import { useDecrementPendingSuggestions } from "@/contexts/UserContext";
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
  formatElapsedTime,
  formatDistanceAxis,
  type UnitSystem,
} from "@/format";

// =============================================================================
// Segments card
// =============================================================================

interface ActivitySegmentsCardProps {
  efforts: ActivitySegmentEffort[];
}

export function ActivitySegmentsCard({ efforts }: ActivitySegmentsCardProps): JSX.Element {
  return (
    <Card>
      <CardContent className="py-4 px-4 space-y-1">
        <div className="text-card-title mb-2">Segments</div>
        {efforts.length === 0 ? (
          <p className="text-body-secondary">No segments crossed on this ride.</p>
        ) : (
          efforts.map((effort) => (
            <Link
              key={effort.id}
              to={`/segments/${effort.segment_id}`}
              className="flex items-center gap-3 py-1.5 px-2 -mx-2 rounded hover:bg-muted transition-colors"
            >
              <SegmentTypeIcon type={effort.segment_type} />
              <span className="font-medium truncate">{effort.segment_name}</span>
              <ClimbCategoryBadge category={effort.climb_category} />
              <span className="ml-auto tabular-nums text-body-secondary">
                {formatElapsedTime(effort.elapsed_time_seconds)}
              </span>
              <span className="text-caption w-14 text-right">
                {effort.is_pr
                  ? ""
                  : effort.delta_to_pr_seconds !== null
                    ? `+${formatElapsedTime(effort.delta_to_pr_seconds)}`
                    : ""}
              </span>
              {effort.is_pr && (
                <span className="text-warning" aria-label="Personal record">★</span>
              )}
            </Link>
          ))
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Inline suggestion card
// =============================================================================

interface SuggestionInlineCardProps {
  suggestion: SegmentSuggestion;
  unitSystem: UnitSystem;
  onDismissed: () => void;
  onApproved: () => void;
}

export function SuggestionInlineCard({
  suggestion,
  unitSystem,
  onDismissed,
  onApproved,
}: SuggestionInlineCardProps): JSX.Element {
  const decrementPendingSuggestions = useDecrementPendingSuggestions();
  const [naming, setNaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissing, setDismissing] = useState(false);
  const [hiddenForSession, setHiddenForSession] = useState(false);

  if (hiddenForSession) return <></>;

  const handleApproved = (): void => {
    setNaming(false);
    decrementPendingSuggestions(1);
    onApproved();
  };

  const handleDismiss = async (): Promise<void> => {
    setDismissing(true);
    try {
      await dismissSuggestion(suggestion.id);
      decrementPendingSuggestions(1);
      onDismissed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dismiss suggestion");
      setDismissing(false);
    }
  };

  return (
    <Card>
      <CardContent className="py-4 px-4 space-y-3">
        <div className="flex items-center gap-2">
          <SegmentTypeIcon type={suggestion.segment_type} />
          <span className="font-medium">Climb Detected</span>
          <ClimbCategoryBadge category={suggestion.climb_category} />
          <span className="text-caption ml-auto">{suggestion.repetition_count}× ridden</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <SegmentMiniMap polyline={suggestion.polyline} height={96} />
          <div className="space-y-2">
            <ElevationProfile
              profile={suggestion.elevation_profile}
              height={48}
              formatDistanceLabel={formatDistanceAxis}
            />
            <div className="text-body-secondary">
              {formatDistance(suggestion.distance_m, unitSystem)} ·{" "}
              {formatElevation(suggestion.elevation_gain_m, unitSystem)} ·{" "}
              {suggestion.avg_grade_pct.toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <Button size="sm" onClick={() => setNaming(true)}>
            Save as Segment
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setHiddenForSession(true)}>
            Later
          </Button>
          <Button size="sm" variant="ghost" onClick={handleDismiss} disabled={dismissing}>
            Dismiss
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <SegmentNamingDialog
          suggestion={suggestion}
          open={naming}
          onOpenChange={setNaming}
          unitSystem={unitSystem}
          onCreated={handleApproved}
        />
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Combined section
// =============================================================================

interface ActivitySegmentsSectionProps {
  data: ActivitySegments | null;
  loading: boolean;
  unitSystem: UnitSystem;
  onSuggestionChange: () => void;
}

export function ActivitySegmentsSection({
  data,
  loading,
  unitSystem,
  onSuggestionChange,
}: ActivitySegmentsSectionProps): JSX.Element | null {
  if (loading) {
    return (
      <Card>
        <CardContent className="py-4 px-4">
          <div className="text-card-title mb-2">Segments</div>
          <div className="h-16 bg-muted rounded animate-pulse" />
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const efforts = data.efforts;
  const suggestion = data.suggestion;

  return (
    <div className="space-y-3">
      {suggestion !== null && (
        <SuggestionInlineCard
          suggestion={suggestion}
          unitSystem={unitSystem}
          onDismissed={onSuggestionChange}
          onApproved={onSuggestionChange}
        />
      )}
      <ActivitySegmentsCard efforts={efforts} />
    </div>
  );
}
