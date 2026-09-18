/**
 * Segments List Page
 *
 * Browse approved segments with type/category/search filters, list and map views.
 * Design from prototype #482 / UX #480 (list: card grid, Variant 1).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { Link } from "react-router-dom";
import { MapContainer, Polyline, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import { fetchSegments } from "@/api/segments";
import type { ClimbCategory, PaginatedSegments, SegmentSummary } from "@/api/segments";
import {
  ClimbCategoryBadge,
  CLIMB_CATEGORY_CONFIG,
  SegmentTypeIcon,
} from "@/components/segments/SegmentBadges";
import { decodePolyline } from "@/components/PolylineMap";
import { useTileConfig } from "@/hooks/useTileUrl";
import { formatDistance, formatElevation, type UnitSystem } from "@/format";

// =============================================================================
// Constants
// =============================================================================

const TYPE_FILTERS = [
  { value: "all", label: "All" },
  { value: "climb", label: "Climbs" },
  { value: "sprint", label: "Sprints" },
  { value: "custom", label: "Custom" },
] as const;

const PER_PAGE = 20;

// =============================================================================
// Segment card (list view)
// =============================================================================

function SegmentCard({ segment, unitSystem }: { segment: SegmentSummary; unitSystem: UnitSystem }): JSX.Element {
  return (
    <Link to={`/segments/${segment.id}`} className="group block">
      <Card className="overflow-hidden hover:border-primary/50 transition-colors">
        <CardContent className="py-4 px-4 space-y-3">
          <div className="flex items-center gap-2 min-w-0">
            <SegmentTypeIcon type={segment.type} />
            <h3 className="font-medium truncate group-hover:text-primary transition-colors">
              {segment.name}
            </h3>
            <div className="ml-auto flex items-center gap-2 flex-shrink-0">
              <ClimbCategoryBadge category={segment.climb_category} />
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>{formatDistance(segment.distance_m, unitSystem)}</span>
            <span>{formatElevation(segment.elevation_gain_m, unitSystem)}</span>
            <span>{segment.avg_grade_pct.toFixed(1)}% avg</span>
            <span className="ml-auto whitespace-nowrap">
              {segment.effort_count.toLocaleString()} efforts · {segment.athlete_count.toLocaleString()}{" "}
              {segment.athlete_count === 1 ? "athlete" : "athletes"}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function SegmentCardSkeleton(): JSX.Element {
  return (
    <Card>
      <CardContent className="py-4 px-4 space-y-3">
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-5" />
          <Skeleton className="h-5 flex-1" />
        </div>
        <div className="flex items-center gap-4">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-12" />
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Map view
// =============================================================================

interface SegmentPositions {
  segment: SegmentSummary;
  positions: [number, number][];
}

interface MapBounds {
  south: number;
  west: number;
  north: number;
  east: number;
}

/** Fit bounds to the current segments whenever the displayed set changes. */
function FitToSegments({ segments }: { segments: SegmentPositions[] }): null {
  const map = useMap();
  const hasFitted = useRef(false);

  useEffect(() => {
    if (hasFitted.current || segments.length === 0) return;
    const all = segments.flatMap((s) => s.positions);
    if (all.length === 0) return;
    const bounds = L.latLngBounds(all.map((p) => L.latLng(p[0], p[1])));
    map.fitBounds(bounds, { padding: [24, 24] });
    hasFitted.current = true;
  }, [segments, map]);

  return null;
}

/** Report the map's viewport bounds to the parent as the user pans/zooms. */
function BoundsReporter({ onBoundsChange }: { onBoundsChange: (bounds: MapBounds) => void }): null {
  useMapEvents({
    moveend: (event) => {
      const b = event.target.getBounds();
      onBoundsChange({
        south: b.getSouth(),
        west: b.getWest(),
        north: b.getNorth(),
        east: b.getEast(),
      });
    },
  });
  return null;
}

function SegmentsMapView({
  segments,
  unitSystem,
  onBoundsChange,
}: {
  segments: SegmentSummary[];
  unitSystem: UnitSystem;
  onBoundsChange: (bounds: MapBounds) => void;
}): JSX.Element {
  const { url: tileUrl, attribution } = useTileConfig();

  const decoded = useMemo<SegmentPositions[]>(() => {
    return segments
      .map((segment) => {
        const positions = segment.polyline ? decodePolyline(segment.polyline) : [];
        return { segment, positions };
      })
      .filter((s) => s.positions.length >= 2);
  }, [segments]);

  if (decoded.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <div className="h-[480px] rounded-lg overflow-hidden bg-muted flex items-center justify-center text-muted-foreground">
            No segment geometry available
          </div>
        </CardContent>
      </Card>
    );
  }

  const first = decoded[0].positions[0];

  return (
    <Card>
      <CardContent className="p-0">
        <div className="relative h-[480px] rounded-lg overflow-hidden">
          <MapContainer center={first} zoom={11} className="absolute inset-0">
            <TileLayer url={tileUrl} attribution={attribution} />
            {decoded.map(({ segment, positions }) => (
              <Polyline
                key={segment.id}
                positions={positions}
                pathOptions={{ color: "#f97316", weight: 4 }}
              >
                <Popup>
                  <Link to={`/segments/${segment.id}`} className="font-medium block">
                    {segment.name}
                  </Link>
                  <div className="text-sm mt-1">
                    {formatDistance(segment.distance_m, unitSystem)} ·{" "}
                    {formatElevation(segment.elevation_gain_m, unitSystem)} ·{" "}
                    {segment.avg_grade_pct.toFixed(1)}%
                  </div>
                </Popup>
              </Polyline>
            ))}
            <FitToSegments segments={decoded} />
            <BoundsReporter onBoundsChange={onBoundsChange} />
          </MapContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Page
// =============================================================================

interface SegmentsPageProps {
  unitSystem: UnitSystem;
}

export function SegmentsPage({ unitSystem }: SegmentsPageProps): JSX.Element {
  const [type, setType] = useState<"all" | SegmentSummary["type"]>("all");
  const [categories, setCategories] = useState<ClimbCategory[]>([]);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [view, setView] = useState<"list" | "map">("list");
  const [page, setPage] = useState(1);
  const [mapBounds, setMapBounds] = useState<MapBounds | null>(null);
  const [data, setData] = useState<PaginatedSegments | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // In map view, results are filtered to the current map viewport.
  const effectiveBounds = useMemo<[number, number, number, number] | undefined>(() => {
    if (view !== "map" || !mapBounds) return undefined;
    return [mapBounds.south, mapBounds.west, mapBounds.north, mapBounds.east];
  }, [view, mapBounds]);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchSegments({
      type: type === "all" ? undefined : type,
      category: categories.length > 0 ? categories : undefined,
      q: search || undefined,
      bounds: effectiveBounds,
      with_polyline: view === "map",
      page,
      per_page: PER_PAGE,
    })
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [type, categories, search, effectiveBounds, view, page]);

  const segments = data?.segments ?? [];
  const pagination = data?.pagination;
  const isEmpty = !isLoading && !error && segments.length === 0;

  const toggleCategory = (c: ClimbCategory): void => {
    setPage(1);
    setCategories((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    );
  };

  const submitSearch = (e: React.FormEvent): void => {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  const handleBoundsChange = (bounds: MapBounds): void => {
    setMapBounds(bounds);
    setPage(1);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-page-title">Segments</h1>
          <p className="text-body-secondary mt-2">Explore climbs and segments</p>
        </div>
        <div className="flex items-center gap-1 bg-muted rounded-lg p-1" role="tablist" aria-label="View">
          {(["list", "map"] as const).map((v) => (
            <button
              key={v}
              role="tab"
              aria-selected={view === v}
              onClick={() => {
                setView(v);
                setPage(1);
              }}
              className={cn(
                "px-3 py-1.5 rounded text-sm font-medium transition-colors capitalize",
                view === v ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1" role="group" aria-label="Segment type">
          {TYPE_FILTERS.map((t) => (
            <button
              key={t.value}
              onClick={() => {
                setType(t.value);
                setPage(1);
              }}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm font-medium transition-colors",
                type === t.value
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {type === "climb" && (
          <div className="flex items-center gap-1 flex-wrap" aria-label="Climb categories">
            {(Object.keys(CLIMB_CATEGORY_CONFIG) as ClimbCategory[]).map((c) => (
              <button
                key={c}
                onClick={() => toggleCategory(c)}
                aria-pressed={categories.includes(c)}
                className={cn(
                  "px-2 py-0.5 rounded text-xs font-bold transition-colors",
                  categories.includes(c)
                    ? "ring-2 ring-primary"
                    : "opacity-70 hover:opacity-100"
                )}
              >
                <span className={cn("px-2 py-0.5 rounded", CLIMB_CATEGORY_CONFIG[c].color)}>
                  {CLIMB_CATEGORY_CONFIG[c].label}
                </span>
              </button>
            ))}
          </div>
        )}

        <form onSubmit={submitSearch} className="ml-auto">
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search segments…"
            className="w-56"
            aria-label="Search segments"
          />
        </form>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          Failed to load segments: {error}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }, (_, i) => (
            <SegmentCardSkeleton key={i} />
          ))}
        </div>
      )}

      {/* Empty */}
      {isEmpty && (
        <EmptyState
          title="No segments found"
          description="Try adjusting your filters, or create a segment from one of your activities."
        />
      )}

      {/* Content */}
      {!isLoading && !error && segments.length > 0 && (
        <>
          {view === "list" ? (
            <div className="space-y-3">
              {segments.map((segment) => (
                <SegmentCard key={segment.id} segment={segment} unitSystem={unitSystem} />
              ))}
            </div>
          ) : (
            <SegmentsMapView
              segments={segments}
              unitSystem={unitSystem}
              onBoundsChange={handleBoundsChange}
            />
          )}

          {/* Pagination */}
          {pagination && pagination.total_pages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-sm text-muted-foreground">
                Page {pagination.page} of {pagination.total_pages} · {pagination.total} segments
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
      )}
    </div>
  );
}