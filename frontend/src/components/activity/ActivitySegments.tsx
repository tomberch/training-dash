/**
 * Activity segments card.
 *
 * Shown on the activity detail page: the segment efforts crossed during
 * the ride. Suggestion approval lives on the dedicated Suggestions page
 * (/suggestions) — the segments endpoint returns only efforts.
 */

import type { JSX } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import type { ActivitySegmentEffort, ActivitySegments } from "@/api/segments";
import { ClimbCategoryBadge, SegmentTypeIcon } from "@/components/segments/SegmentBadges";
import { formatElapsedTime } from "@/format";

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
// Combined section
// =============================================================================

interface ActivitySegmentsSectionProps {
  data: ActivitySegments | null;
  loading: boolean;
}

export function ActivitySegmentsSection({
  data,
  loading,
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

  // The segments endpoint returns only efforts — suggestion approval lives
  // on the dedicated Suggestions page (/suggestions).
  return <ActivitySegmentsCard efforts={data.efforts} />;
}
