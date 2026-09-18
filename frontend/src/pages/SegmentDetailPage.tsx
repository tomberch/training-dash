/**
 * Segment Detail Page
 *
 * Two-column layout (UX #481 Variant 2): map + gradient profile + efforts table
 * on the left; PR card + stats + owner actions on the right.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { cn } from "@/lib/utils";
import {
  deleteSegment,
  fetchSegment,
  fetchSegmentEfforts,
  updateSegmentName,
} from "@/api/segments";
import type {
  PaginatedEfforts,
  SegmentDetailData,
  SegmentEffort,
} from "@/api/segments";
import {
  ClimbCategoryBadge,
  SegmentTypeIcon,
} from "@/components/segments/SegmentBadges";
import { ElevationProfile } from "@/components/segments/ElevationProfile";
import { decodePolyline } from "@/components/PolylineMap";
import { useTileConfig } from "@/hooks/useTileUrl";
import {
  formatDistance,
  formatElevation,
  formatElapsedTime,
  formatDate,
  formatTimeDelta,
  type UnitSystem,
} from "@/format";

const PER_PAGE = 20;

// =============================================================================
// Map
// =============================================================================

function FitToPolyline({ positions }: { positions: [number, number][] }): null {
  const map = useMap();
  const hasFitted = useRef(false);

  useEffect(() => {
    if (hasFitted.current || positions.length < 2) return;
    const bounds = L.latLngBounds(positions.map((p) => L.latLng(p[0], p[1])));
    map.fitBounds(bounds, { padding: [24, 24] });
    hasFitted.current = true;
  }, [positions, map]);

  return null;
}

function SegmentMap({ polyline }: { polyline: string }): JSX.Element {
  const { url: tileUrl, attribution } = useTileConfig();
  const positions = useMemo(() => decodePolyline(polyline), [polyline]);

  if (positions.length < 2) {
    return (
      <div className="h-64 rounded-t-lg bg-muted flex items-center justify-center text-muted-foreground">
        No GPS data
      </div>
    );
  }

  return (
    <MapContainer center={positions[0]} zoom={13} className="h-64 rounded-t-lg">
      <TileLayer url={tileUrl} attribution={attribution} />
      <Polyline positions={positions} pathOptions={{ color: "#f97316", weight: 5 }} />
      <Marker position={positions[0]} />
      <Marker position={positions[positions.length - 1]} />
      <FitToPolyline positions={positions} />
    </MapContainer>
  );
}

// =============================================================================
// Efforts table
// =============================================================================

type EffortsSort = "time" | "date" | "power";

interface EffortsTableProps {
  efforts: SegmentEffort[];
  prSeconds: number | null;
  sort: EffortsSort;
  order: "asc" | "desc";
  onSortChange: (sort: EffortsSort) => void;
  onNavigateToActivity: (activityId: string) => void;
}

function SortHeader({
  label,
  column,
  sort,
  order,
  onSortChange,
}: {
  label: string;
  column: EffortsSort;
  sort: EffortsSort;
  order: "asc" | "desc";
  onSortChange: (sort: EffortsSort) => void;
}): JSX.Element {
  const active = sort === column;
  return (
    <button
      className={cn(
        "inline-flex items-center gap-1 hover:text-foreground transition-colors",
        active && "text-foreground"
      )}
      onClick={() => onSortChange(column)}
    >
      {label}
      <span className={cn("text-xs", active ? "opacity-100" : "opacity-30")}>
        {active ? (order === "asc" ? "▲" : "▼") : "▲"}
      </span>
    </button>
  );
}

function EffortsTable({
  efforts,
  prSeconds,
  sort,
  order,
  onSortChange,
  onNavigateToActivity,
}: EffortsTableProps): JSX.Element {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground border-b">
          <th className="pb-2" aria-sort={sort === "time" ? (order === "asc" ? "ascending" : "descending") : "none"}>
            <SortHeader label="Time" column="time" sort={sort} order={order} onSortChange={onSortChange} />
          </th>
          <th className="pb-2">+/-</th>
          <th className="pb-2" aria-sort={sort === "power" ? (order === "asc" ? "ascending" : "descending") : "none"}>
            <SortHeader label="Power" column="power" sort={sort} order={order} onSortChange={onSortChange} />
          </th>
          <th className="pb-2">HR</th>
          <th className="pb-2" aria-sort={sort === "date" ? (order === "asc" ? "ascending" : "descending") : "none"}>
            <SortHeader label="Date" column="date" sort={sort} order={order} onSortChange={onSortChange} />
          </th>
        </tr>
      </thead>
      <tbody>
        {efforts.map((effort) => (
          <tr
            key={effort.id}
            className={cn(
              "border-b last:border-0 cursor-pointer hover:bg-muted/50 transition-colors",
              effort.is_pr && "bg-amber-500/5"
            )}
            onClick={() => onNavigateToActivity(effort.activity_id)}
          >
            <td className="py-2 font-mono">
              {effort.is_pr && <span className="text-amber-500 mr-1">★</span>}
              {formatElapsedTime(effort.elapsed_time_seconds)}
            </td>
            <td className="py-2 text-muted-foreground">
              {effort.is_pr
                ? "PR"
                : prSeconds !== null
                  ? formatTimeDelta(effort.elapsed_time_seconds, prSeconds)
                  : ""}
            </td>
            <td className="py-2">{effort.avg_power_watts ?? "—"}</td>
            <td className="py-2">{effort.avg_hr_bpm ?? "—"}</td>
            <td className="py-2 text-muted-foreground">{formatDate(effort.started_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// =============================================================================
// Page
// =============================================================================

interface SegmentDetailPageProps {
  unitSystem: UnitSystem;
  currentUserId: number;
}

export function SegmentDetailPage({ unitSystem, currentUserId }: SegmentDetailPageProps): JSX.Element {
  const { segmentId } = useParams<{ segmentId: string }>();
  const navigate = useNavigate();
  const [segment, setSegment] = useState<SegmentDetailData | null>(null);
  const [effortsData, setEffortsData] = useState<PaginatedEfforts | null>(null);
  const [sort, setSort] = useState<EffortsSort>("time");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [effortsError, setEffortsError] = useState<string | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);

  const isOwner = segment?.created_by === currentUserId;
  const prSeconds = segment?.my_stats?.pr_time_seconds ?? null;

  useEffect(() => {
    if (!segmentId) return;
    setError(null);
    setSegment(null);
    setEffortsData(null);
    setPage(1);
    fetchSegment(segmentId)
      .then(setSegment)
      .catch((err: Error) => setError(err.message));
  }, [segmentId]);

  useEffect(() => {
    if (!segmentId) return;
    setEffortsError(null);
    fetchSegmentEfforts(segmentId, { sort, order, page, per_page: PER_PAGE })
      .then(setEffortsData)
      .catch((err: Error) => setEffortsError(err.message));
  }, [segmentId, sort, order, page]);

  const handleSortChange = (column: EffortsSort): void => {
    setPage(1);
    if (sort === column) {
      setOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSort(column);
      setOrder("asc");
    }
  };

  const handleRenameSave = async (): Promise<void> => {
    if (!segmentId || !nameDraft.trim()) return;
    try {
      const updated = await updateSegmentName(segmentId, nameDraft.trim());
      setSegment(updated);
      setIsRenaming(false);
      setNameError(null);
    } catch (err) {
      setNameError(err instanceof Error ? err.message : "Failed to rename");
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (!segmentId) return;
    try {
      await deleteSegment(segmentId);
      navigate("/segments");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete segment");
    }
  };

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          Failed to load segment: {error}
        </div>
      </div>
    );
  }

  if (!segment) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-4">
            <Skeleton className="h-64" />
            <Skeleton className="h-24" />
            <Skeleton className="h-48" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-40" />
            <Skeleton className="h-64" />
          </div>
        </div>
      </div>
    );
  }

  const efforts = effortsData?.efforts ?? [];
  const pagination = effortsData?.pagination;
  const hasEfforts = (segment.my_stats?.effort_count ?? 0) > 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          {isRenaming ? (
            <div className="flex items-center gap-2">
              <Input
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                className="max-w-md"
                aria-label="Segment name"
                autoFocus
              />
              <Button size="sm" onClick={handleRenameSave}>Save</Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setIsRenaming(false);
                  setNameError(null);
                }}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <SegmentTypeIcon type={segment.type} />
              <h1 className="text-page-title truncate">{segment.name}</h1>
              <ClimbCategoryBadge category={segment.climb_category} />
            </div>
          )}
          {nameError && <p className="text-destructive text-sm mt-1">{nameError}</p>}
          <div className="text-body-secondary mt-2">
            {formatDistance(segment.distance_m, unitSystem)} ·{" "}
            {formatElevation(segment.elevation_gain_m, unitSystem)} ·{" "}
            {segment.avg_grade_pct.toFixed(1)}% avg grade
          </div>
        </div>

        {isOwner && !isRenaming && (
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setNameDraft(segment.name);
                setIsRenaming(true);
              }}
            >
              Rename
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="text-destructive">
                  Delete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete this segment?</AlertDialogTitle>
                  <AlertDialogDescription>
                    "{segment.name}" and all its efforts will be removed. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    onClick={handleDelete}
                  >
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: map, gradient profile, efforts */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardContent className="p-0">
              <SegmentMap polyline={segment.polyline} />
              <div className="p-4">
                <h3 className="text-sm font-medium mb-2">Elevation Profile</h3>
                <ElevationProfile
                  profile={segment.elevation_profile}
                  height={200}
                  formatDistanceLabel={(m) => formatDistance(m, unitSystem)}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Your Efforts</CardTitle>
            </CardHeader>
            <CardContent>
              {effortsError ? (
                <div className="bg-destructive/10 text-destructive p-3 rounded-lg text-sm">
                  Failed to load efforts: {effortsError}
                </div>
              ) : hasEfforts ? (
                <>
                  <EffortsTable
                    efforts={efforts}
                    prSeconds={prSeconds}
                    sort={sort}
                    order={order}
                    onSortChange={handleSortChange}
                    onNavigateToActivity={(activityId) => navigate(`/activities/${activityId}`)}
                  />
                  {pagination && pagination.total_pages > 1 && (
                    <div className="flex items-center justify-between mt-4">
                      <span className="text-sm text-muted-foreground">
                        Page {pagination.page} of {pagination.total_pages}
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
                          disabled={page >= pagination.total_pages}
                          onClick={() => setPage((p) => p + 1)}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <EmptyState
                  title="You haven't ridden this segment yet"
                  description="Efforts appear here automatically after you ride it."
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column: PR card, stats, actions */}
        <div className="space-y-6">
          {hasEfforts && segment.my_stats && segment.my_stats.pr_time_seconds !== null && (
            <Card className="border-amber-500/30 bg-amber-500/5">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <span className="text-amber-500">★</span> Your PR
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-amber-600 mb-2">
                  {formatElapsedTime(segment.my_stats.pr_time_seconds)}
                </div>
                <div className="text-sm text-muted-foreground">
                  {segment.my_stats.effort_count}{" "}
                  {segment.my_stats.effort_count === 1 ? "effort" : "efforts"}
                </div>
                {segment.my_stats.pr_date && (
                  <div className="text-caption mt-1">
                    {formatDate(segment.my_stats.pr_date)}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Segment Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Distance</span>
                <span className="font-medium">{formatDistance(segment.distance_m, unitSystem)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Elevation</span>
                <span className="font-medium">{formatElevation(segment.elevation_gain_m, unitSystem)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Avg Grade</span>
                <span className="font-medium">{segment.avg_grade_pct.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Max Grade</span>
                <span className="font-medium">{segment.max_grade_pct.toFixed(1)}%</span>
              </div>
              <div className="border-t pt-3 mt-3 space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Total Efforts</span>
                  <span className="font-medium">{segment.effort_count.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Athletes</span>
                  <span className="font-medium">{segment.athlete_count.toLocaleString()}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}