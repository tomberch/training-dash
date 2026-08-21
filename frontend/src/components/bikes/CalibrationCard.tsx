/**
 * CalibrationCard - Shows CdA calibration status and trigger for a bike
 */
import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getCalibrationStatus, type CalibrationStatus } from "@/api/bikes";
import type { Bike } from "@/api/types";

interface CalibrationCardProps {
  bike: Bike;
  onCalibrate: () => void;
}

const CONFIDENCE_COLORS = {
  high: "bg-success/20 text-success",
  medium: "bg-warning/20 text-warning",
  low: "bg-muted text-muted-foreground",
};

const CONFIDENCE_LABELS = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

export function CalibrationCard({ bike, onCalibrate }: CalibrationCardProps) {
  const [status, setStatus] = useState<CalibrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadStatus() {
      setLoading(true);
      setError(null);
      try {
        const data = await getCalibrationStatus(bike.id);
        setStatus(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load status");
      } finally {
        setLoading(false);
      }
    }
    loadStatus();
  }, [bike.id]);

  // Determine CdA source badge
  const getCdaSourceBadge = () => {
    if (bike.cda_source === "calibrated") {
      return (
        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-success/20 text-success">
          Calibrated
        </span>
      );
    }
    if (bike.cda_source === "manual") {
      return (
        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-primary/20 text-primary">
          Manual
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-muted text-muted-foreground">
        Default
      </span>
    );
  };

  // Format last calibrated date
  const formatLastCalibrated = (dateStr: string | null) => {
    if (!dateStr) return "Never";
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>CdA Calibration</CardTitle>
          <CardDescription>Loading calibration status...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-10 w-32" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>CdA Calibration</CardTitle>
          <CardDescription className="text-destructive">{error}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>CdA Calibration</CardTitle>
            <CardDescription>
              Estimate aerodynamic drag from your ride data
            </CardDescription>
          </div>
          {getCdaSourceBadge()}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Current CdA value */}
        <div className="flex items-baseline gap-2">
          <span className="text-metric">
            {bike.cda !== null ? bike.cda.toFixed(3) : "—"}
          </span>
          <span className="text-body-secondary">m²</span>
        </div>

        {/* Last calibrated */}
        {bike.calibrated_at && (
          <p className="text-caption">
            Last calibrated: {formatLastCalibrated(bike.calibrated_at)}
          </p>
        )}

        {/* Status info */}
        {status && (
          <div className="space-y-2">
            {status.eligible ? (
              <>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "px-2 py-0.5 text-xs font-medium rounded-full",
                      CONFIDENCE_COLORS[status.estimated_confidence]
                    )}
                  >
                    {CONFIDENCE_LABELS[status.estimated_confidence]}
                  </span>
                  <span className="text-caption">
                    ({status.n_activities} activities available)
                  </span>
                </div>
                <Button onClick={onCalibrate} className="mt-2">
                  Calibrate Now
                </Button>
              </>
            ) : (
              <div className="p-3 rounded-lg bg-muted text-body-secondary text-sm">
                <p>{status.reason}</p>
                {status.reason?.includes("tagged") && (
                  <p className="mt-1 text-caption">
                    Tip: Tag your rides to this bike from the activity detail page.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Help text */}
        <details className="text-caption">
          <summary className="cursor-pointer hover:text-foreground transition-colors">
            What is CdA calibration?
          </summary>
          <div className="mt-2 space-y-1 pl-2 border-l-2 border-muted">
            <p>
              CdA (Coefficient of Drag × Area) measures how aerodynamic you are on
              the bike. A lower CdA means less air resistance and faster speeds at
              the same power.
            </p>
            <p>
              Calibration analyzes your rides to estimate your CdA from steady-state
              segments where you're riding at 30+ km/h on flat terrain with consistent
              power.
            </p>
            <p>
              Requirements: rides with power data, speed &gt;30 km/h, flat terrain
              (&lt;2% grade), steady effort for 60+ seconds.
            </p>
          </div>
        </details>
      </CardContent>
    </Card>
  );
}
