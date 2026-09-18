/**
 * SegmentCreationModal
 *
 * Split-view modal for manually creating a segment from an activity's GPS
 * track (UX #481 Creation Variant 2). Click the map to set start/end points,
 * preview the computed geometry, name it, and create.
 */

import { useEffect, useMemo, useState } from "react";
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, Marker, Polyline, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { createSegment, SegmentDuplicateError } from "@/api/segments";
import type { GeoJSONFeatureCollection } from "@/api";
import {
  ClimbCategoryBadge,
  SegmentTypeIcon,
} from "@/components/segments/SegmentBadges";
import { ElevationProfile } from "@/components/segments/ElevationProfile";
import { FitToPositions } from "@/components/segments/FitToPositions";
import { computeSegmentPreview, nearestFeatureIndex } from "@/lib/segmentPreview";
import type { PreviewStats } from "@/lib/segmentPreview";
import { useTileConfig } from "@/hooks/useTileUrl";
import { formatDistance, formatElevation, formatDistanceAxis, type UnitSystem } from "@/format";

interface SegmentCreationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activityId: string;
  geojson: GeoJSONFeatureCollection;
  unitSystem: UnitSystem;
}

function startIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="background:#10b981;width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function endIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="background:#ef4444;width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

interface PointSelectionMapProps {
  features: GeoJSONFeatureCollection["features"];
  startIndex: number | null;
  endIndex: number | null;
  onSelect: (index: number) => void;
}

function PointSelectionMap({ features, startIndex, endIndex, onSelect }: PointSelectionMapProps): JSX.Element {
  const { url: tileUrl, attribution } = useTileConfig();

  const positions = useMemo<[number, number][]>(
    () =>
      features
        .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
        .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]),
    [features]
  );

  useMapEvents({
    click: (e) => {
      const idx = nearestFeatureIndex(features, e.latlng.lat, e.latlng.lng);
      if (idx !== null) onSelect(idx);
    },
  });

  const startFeature = startIndex !== null ? features[startIndex] : null;
  const endFeature = endIndex !== null ? features[endIndex] : null;
  const startPos =
    startFeature?.geometry && startFeature.geometry.coordinates.length >= 2
      ? ([startFeature.geometry.coordinates[1], startFeature.geometry.coordinates[0]] as [number, number])
      : null;
  const endPos =
    endFeature?.geometry && endFeature.geometry.coordinates.length >= 2
      ? ([endFeature.geometry.coordinates[1], endFeature.geometry.coordinates[0]] as [number, number])
      : null;
  const previewPositions =
    startIndex !== null && endIndex !== null
      ? features
          .slice(Math.min(startIndex, endIndex), Math.max(startIndex, endIndex) + 1)
          .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
          .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number])
      : [];

  return (
    <>
      <TileLayer url={tileUrl} attribution={attribution} />
      <Polyline positions={positions} pathOptions={{ color: "#6366f1", weight: 3 }} />
      {previewPositions.length >= 2 && (
        <Polyline positions={previewPositions} pathOptions={{ color: "#f97316", weight: 5 }} />
      )}
      {startPos && <Marker position={startPos} icon={startIcon()} />}
      {endPos && <Marker position={endPos} icon={endIcon()} />}
    </>
  );
}

export function SegmentCreationModal({
  open,
  onOpenChange,
  activityId,
  geojson,
  unitSystem,
}: SegmentCreationModalProps): JSX.Element {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [startIndex, setStartIndex] = useState<number | null>(null);
  const [endIndex, setEndIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [duplicateId, setDuplicateId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const positions = useMemo<[number, number][]>(
    () =>
      geojson.features
        .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
        .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]),
    [geojson]
  );

  // Reset on open
  useEffect(() => {
    if (open) {
      setName("");
      setStartIndex(null);
      setEndIndex(null);
      setError(null);
      setDuplicateId(null);
      setSubmitting(false);
    }
  }, [open]);

  const preview: PreviewStats | null = useMemo(() => {
    if (startIndex === null || endIndex === null || startIndex === endIndex) return null;
    const lo = Math.min(startIndex, endIndex);
    const hi = Math.max(startIndex, endIndex);
    return computeSegmentPreview(geojson.features, lo, hi);
  }, [geojson, startIndex, endIndex]);

  const handleMapSelect = (index: number): void => {
    setError(null);
    setDuplicateId(null);
    if (startIndex === null) {
      setStartIndex(index);
    } else if (endIndex === null) {
      setEndIndex(index);
    } else {
      // Restart selection from scratch
      setStartIndex(index);
      setEndIndex(null);
    }
  };

  const clearSelection = (): void => {
    setStartIndex(null);
    setEndIndex(null);
    setError(null);
    setDuplicateId(null);
  };

  const canCreate =
    name.trim().length >= 3 &&
    name.trim().length <= 100 &&
    startIndex !== null &&
    endIndex !== null &&
    startIndex < endIndex;

  const orderError =
    startIndex !== null && endIndex !== null && startIndex >= endIndex
      ? "End point must come after the start point"
      : null;

  const submit = async (): Promise<void> => {
    if (startIndex === null || endIndex === null || startIndex >= endIndex) return;
    setError(null);
    setDuplicateId(null);
    setSubmitting(true);
    try {
      const segment = await createSegment({
        name: name.trim(),
        activity_id: activityId,
        start_index: startIndex,
        end_index: endIndex,
      });
      toast("Segment created");
      onOpenChange(false);
      navigate(`/segments/${segment.id}`);
    } catch (err) {
      if (err instanceof SegmentDuplicateError) {
        setDuplicateId(err.duplicateSegmentId);
        setError(err.message);
      } else {
        const message = err instanceof Error ? err.message : "Failed to create segment";
        setError(message);
      }
      setSubmitting(false);
    }
  };

  const center = positions.length > 0 ? positions[0] : ([0, 0] as [number, number]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Create Segment</DialogTitle>
          <DialogDescription>
            Click the map to set the start point, then click again to set the end point.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Left: map */}
          <div className="relative h-[320px] rounded-lg overflow-hidden border border-border">
            {positions.length >= 2 ? (
              <MapContainer center={center} zoom={13} className="absolute inset-0">
                <PointSelectionMap
                  features={geojson.features}
                  startIndex={startIndex}
                  endIndex={endIndex}
                  onSelect={handleMapSelect}
                />
                <FitToPositions positions={positions} padding={16} />
              </MapContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                No GPS data available
              </div>
            )}
          </div>

          {/* Right: form */}
          <div className="space-y-3">
            {/* Selection card */}
            <Card>
              <CardContent className="py-3 px-4 space-y-2">
                <div className="text-sm font-medium">Selection</div>
                <div className="flex items-center justify-between">
                  <span className="text-body-secondary">
                    Start: {startIndex !== null ? `record #${startIndex}` : "not set"}
                  </span>
                  {startIndex !== null && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setStartIndex(null);
                        setError(null);
                        setDuplicateId(null);
                      }}
                    >
                      Adjust
                    </Button>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-body-secondary">
                    End: {endIndex !== null ? `record #${endIndex}` : "not set"}
                  </span>
                  {endIndex !== null && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setEndIndex(null);
                        setError(null);
                        setDuplicateId(null);
                      }}
                    >
                      Adjust
                    </Button>
                  )}
                </div>
                {(startIndex !== null || endIndex !== null) && (
                  <Button variant="ghost" size="sm" onClick={clearSelection}>
                    Clear selection
                  </Button>
                )}
              </CardContent>
            </Card>

            {/* Preview card */}
            {preview && (
              <Card>
                <CardContent className="py-3 px-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <SegmentTypeIcon type={preview.type} />
                    <ClimbCategoryBadge category={preview.climb_category} />
                    <span className="text-sm capitalize">{preview.type}</span>
                  </div>
                  <div className="text-body-secondary">
                    {formatDistance(preview.distance_m, unitSystem)} ·{" "}
                    {formatElevation(preview.elevation_gain_m, unitSystem)} ·{" "}
                    {preview.avg_grade_pct.toFixed(1)}% avg ·{" "}
                    {preview.max_grade_pct.toFixed(1)}% max
                  </div>
                  <ElevationProfile
                    profile={preview.elevation_profile}
                    height={40}
                    formatDistanceLabel={formatDistanceAxis}
                  />
                </CardContent>
              </Card>
            )}

            {/* Name input */}
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Segment name (3-100 characters)"
              aria-label="Segment name"
              minLength={3}
              maxLength={100}
            />

            {orderError && <p className="text-sm text-destructive">{orderError}</p>}
            {error && <p className="text-sm text-destructive">{error}</p>}
            {duplicateId && (
              <p className="text-body-secondary">
                A similar segment already exists.{" "}
                <button className="text-primary underline" onClick={() => navigate(`/segments/${duplicateId}`)}>
                  View it
                </button>
              </p>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canCreate || submitting}>
            {submitting ? "Creating…" : "Create Segment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
