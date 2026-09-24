/**
 * Shared "Name your segment" dialog used when approving a suggestion.
 *
 * Single combined step: a large interactive map (the source activity's GPS
 * track with the suggested climb highlighted) where start/end can be
 * fine-tuned by clicking the track, a live stats preview, and the name
 * input. Approving submits the (possibly adjusted) indices so the backend
 * recomputes geometry.
 */

import { useEffect, useMemo, useState } from "react";
import type { JSX } from "react";
import { MapContainer, Marker, Polyline, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import type { SegmentSuggestion } from "@/api/suggestions";
import { approveSuggestion } from "@/api/suggestions";
import { fetchActivityRecords } from "@/api/activities";
import type { GeoJSONFeatureCollection } from "@/api";
import { FitToPositions } from "@/components/segments/FitToPositions";
import { useTileConfig } from "@/hooks/useTileUrl";
import { computeSegmentPreview, nearestFeatureIndex } from "@/lib/segmentPreview";
import { formatDistance, formatElevation, type UnitSystem } from "@/format";

interface SegmentNamingDialogProps {
  suggestion: SegmentSuggestion | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  unitSystem: UnitSystem;
  onCreated: (segmentId: string) => void;
}

function startIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="background:#10b981;width:22px;height:22px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function endIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="background:#ef4444;width:22px;height:22px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

interface TrackMapProps {
  features: GeoJSONFeatureCollection["features"];
  /** Selection index in ORIGINAL feature space (as stored/returned). */
  startIndex: number | null;
  endIndex: number | null;
  /** Called with an index in ORIGINAL feature space. */
  onSelect: (index: number) => void;
}

function TrackMap({ features, startIndex, endIndex, onSelect }: TrackMapProps): JSX.Element {
  const { url: tileUrl, attribution } = useTileConfig();

  // Map original feature index -> position, skipping invalid features once
  // (GPS dropouts). Selection indices stay in original space end-to-end:
  // nearestFeatureIndex, computeSegmentPreview and the backend all use the
  // unfiltered feature array, so only rendering translates through this map.
  const indexToPosition = useMemo<Map<number, [number, number]>>(() => {
    const map = new Map<number, [number, number]>();
    features.forEach((f, index) => {
      if (f.geometry !== null && f.geometry.coordinates.length >= 2) {
        map.set(index, [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]);
      }
    });
    return map;
  }, [features]);

  useMapEvents({
    click: (e) => {
      const idx = nearestFeatureIndex(features, e.latlng.lat, e.latlng.lng);
      if (idx !== null) onSelect(idx);
    },
  });

  const startPos = startIndex !== null ? indexToPosition.get(startIndex) : undefined;
  const endPos = endIndex !== null ? indexToPosition.get(endIndex) : undefined;
  const previewPositions =
    startIndex !== null && endIndex !== null
      ? [...indexToPosition.entries()]
          .filter(([index]) => index >= Math.min(startIndex, endIndex) && index <= Math.max(startIndex, endIndex))
          .map(([, pos]) => pos)
      : [];

  return (
    <>
      <TileLayer url={tileUrl} attribution={attribution} />
      <Polyline
        positions={[...indexToPosition.values()]}
        pathOptions={{ color: "#6364f1", weight: 3, opacity: 0.5 }}
      />
      {previewPositions.length >= 2 && (
        <Polyline positions={previewPositions} pathOptions={{ color: "#f97316", weight: 5 }} />
      )}
      {startPos && <Marker position={startPos} icon={startIcon()} />}
      {endPos && <Marker position={endPos} icon={endIcon()} />}
    </>
  );
}

export function SegmentNamingDialog({
  suggestion,
  open,
  onOpenChange,
  unitSystem,
  onCreated,
}: SegmentNamingDialogProps): JSX.Element | null {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [geojson, setGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [trackError, setTrackError] = useState<string | null>(null);
  const [adjusting, setAdjusting] = useState<"start" | "end" | null>(null);
  const [startIndex, setStartIndex] = useState<number | null>(null);
  const [endIndex, setEndIndex] = useState<number | null>(null);

  // Reset + lazily fetch the source activity's GPS track when the dialog opens
  useEffect(() => {
    setName("");
    setError(null);
    setSubmitting(false);
    setTrackError(null);
    setAdjusting(null);
    setStartIndex(null);
    setEndIndex(null);
    setGeojson(null);
    if (open && suggestion?.source_activity_id) {
      fetchActivityRecords(suggestion.source_activity_id)
        .then((data) => {
          setGeojson(data);
          // Default selection: the detected climb itself. The suggestion's
          // start/end points snap to their nearest track indices, so the
          // preview matches what was detected. If snapping fails (geometry
          // predates the track, or both endpoints snap to one point), send
          // NO indices on approve — the backend then keeps the detected
          // geometry instead of silently redefining the segment.
          const features = data.features;
          const startIdx = nearestFeatureIndex(
            features,
            suggestion.start_point.lat,
            suggestion.start_point.lng
          );
          const endIdx = nearestFeatureIndex(
            features,
            suggestion.end_point.lat,
            suggestion.end_point.lng
          );
          if (startIdx !== null && endIdx !== null && startIdx !== endIdx) {
            setStartIndex(Math.min(startIdx, endIdx));
            setEndIndex(Math.max(startIdx, endIdx));
          }
        })
        .catch(() => setTrackError("Could not load the source activity track"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, suggestion]);

  if (!suggestion) return null;

  const trackPositions: [number, number][] =
    geojson?.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]) ?? [];

  const preview =
    geojson && startIndex !== null && endIndex !== null
      ? computeSegmentPreview(geojson.features, Math.min(startIndex, endIndex), Math.max(startIndex, endIndex))
      : null;

  const handleMapSelect = (index: number): void => {
    setError(null);
    if (adjusting === "start") {
      setStartIndex(index);
      setAdjusting(null);
    } else if (adjusting === "end") {
      setEndIndex(index);
      setAdjusting(null);
    }
    // Without an active adjust mode, a click does nothing — the user must
    // pick which endpoint to move first, avoiding surprise edits.
  };

  const submit = async (): Promise<void> => {
    setError(null);
    setSubmitting(true);
    try {
      const options =
        startIndex !== null && endIndex !== null
          ? { start_index: startIndex, end_index: endIndex }
          : undefined;
      const segment = await approveSuggestion(suggestion.id, name.trim(), options);
      toast("Segment created");
      onOpenChange(false);
      onCreated(segment.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create segment");
      setSubmitting(false);
    }
  };

  const center: [number, number] =
    trackPositions.length > 0
      ? trackPositions[0]
      : [suggestion.start_point.lat, suggestion.start_point.lng];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Name your segment</DialogTitle>
          <DialogDescription>
            {preview
              ? `${formatDistance(preview.distance_m, unitSystem)} · ${formatElevation(
                  preview.elevation_gain_m,
                  unitSystem
                )} · ${preview.avg_grade_pct.toFixed(1)}% avg grade`
              : `${formatDistance(suggestion.distance_m, unitSystem)} · ${suggestion.avg_grade_pct.toFixed(
                  1
                )}% avg grade`}
          </DialogDescription>
        </DialogHeader>

        {suggestion.source_activity_id ? (
          trackError ? (
            <p className="text-sm text-destructive">{trackError}</p>
          ) : (
            <div className="space-y-2">
              <div className="relative h-[320px] rounded-lg overflow-hidden border border-border">
                {trackPositions.length >= 2 && geojson ? (
                  <MapContainer center={center} zoom={13} className="absolute inset-0">
                    <TrackMap
                      features={geojson.features}
                      startIndex={startIndex}
                      endIndex={endIndex}
                      onSelect={handleMapSelect}
                    />
                    <FitToPositions positions={trackPositions} padding={16} />
                  </MapContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                    Loading track…
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-body-secondary">
                  {adjusting === "start"
                    ? "Click the track to set the start point"
                    : adjusting === "end"
                      ? "Click the track to set the end point"
                      : "Adjust endpoints if the detected climb needs fine-tuning"}
                </span>
                <span className="ml-auto flex gap-2">
                  <Button
                    size="sm"
                    variant={adjusting === "start" ? "default" : "outline"}
                    onClick={() => setAdjusting(adjusting === "start" ? null : "start")}
                  >
                    Move Start
                  </Button>
                  <Button
                    size="sm"
                    variant={adjusting === "end" ? "default" : "outline"}
                    onClick={() => setAdjusting(adjusting === "end" ? null : "end")}
                  >
                    Move End
                  </Button>
                </span>
              </div>
            </div>
          )
        ) : (
          <p className="text-sm text-muted-foreground">
            The detected geometry will be used as-is (no source track available).
          </p>
        )}

        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Segment name"
          aria-label="Segment name"
          minLength={3}
          maxLength={100}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={submitting || name.trim().length < 3}>
            {submitting ? "Creating…" : "Create Segment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}