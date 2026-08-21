/**
 * CalibrationModal - Modal for running CdA calibration with progress and results
 */
import { useState } from "react";
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
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { calibrateBike, type CalibrationResult, type CalibrateRequest } from "@/api/bikes";
import type { Bike } from "@/api/types";

interface CalibrationModalProps {
  open: boolean;
  onClose: () => void;
  bike: Bike;
  onCalibrationComplete: (result: CalibrationResult) => void;
}

type CalibrationState = "config" | "running" | "success" | "error";

const CONFIDENCE_COLORS = {
  high: "bg-success/20 text-success border-success/30",
  medium: "bg-warning/20 text-warning border-warning/30",
  low: "bg-muted text-muted-foreground border-muted",
};

const CONFIDENCE_DESCRIPTIONS = {
  high: "Excellent data quality. CdA estimate is reliable.",
  medium: "Good data quality. CdA estimate is reasonably accurate.",
  low: "Limited data. Consider gathering more steady-state segments.",
};

export function CalibrationModal({
  open,
  onClose,
  bike,
  onCalibrationComplete,
}: CalibrationModalProps) {
  const [state, setState] = useState<CalibrationState>("config");
  const [riderMass, setRiderMass] = useState<string>("");
  const [minConfidence, setMinConfidence] = useState<"low" | "medium" | "high">("medium");
  const [result, setResult] = useState<CalibrationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => {
    // Reset state when closing
    setState("config");
    setResult(null);
    setError(null);
    onClose();
  };

  const handleCalibrate = async () => {
    setState("running");
    setError(null);

    const request: CalibrateRequest = {
      min_confidence: minConfidence,
    };

    // Add rider mass if provided
    const massNum = parseFloat(riderMass);
    if (!isNaN(massNum) && massNum > 0) {
      request.rider_mass_kg = massNum;
    }

    try {
      const res = await calibrateBike(bike.id, request);
      setResult(res);
      setState("success");
      onCalibrationComplete(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calibration failed");
      setState("error");
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (mins === 0) return `${secs}s`;
    return `${mins}m ${secs}s`;
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Calibrate CdA for {bike.name}</DialogTitle>
          <DialogDescription>
            {state === "config" && "Configure calibration settings and run analysis"}
            {state === "running" && "Analyzing your ride data..."}
            {state === "success" && "Calibration complete"}
            {state === "error" && "Calibration failed"}
          </DialogDescription>
        </DialogHeader>

        {/* Configuration state */}
        {state === "config" && (
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="rider-mass">Rider Mass (kg)</Label>
              <Input
                id="rider-mass"
                type="number"
                placeholder="75"
                value={riderMass}
                onChange={(e) => setRiderMass(e.target.value)}
              />
              <p className="text-caption">
                Your body weight. Leave blank to use default (75 kg).
              </p>
            </div>

            <div className="space-y-2">
              <Label>Minimum Confidence</Label>
              <div className="flex gap-2">
                {(["low", "medium", "high"] as const).map((conf) => (
                  <button
                    key={conf}
                    type="button"
                    onClick={() => setMinConfidence(conf)}
                    className={cn(
                      "px-3 py-1.5 text-sm font-medium rounded-md border transition-colors",
                      minConfidence === conf
                        ? CONFIDENCE_COLORS[conf]
                        : "bg-background border-border hover:bg-muted"
                    )}
                  >
                    {conf.charAt(0).toUpperCase() + conf.slice(1)}
                  </button>
                ))}
              </div>
              <p className="text-caption">
                Only update bike CdA if confidence meets this threshold.
              </p>
            </div>
          </div>
        )}

        {/* Running state */}
        {state === "running" && (
          <div className="py-8 flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-body-secondary">
              Analyzing {bike.name} rides for calibration segments...
            </p>
          </div>
        )}

        {/* Success state */}
        {state === "success" && result && (
          <div className="space-y-4 py-4">
            {/* CdA result */}
            <div className="flex items-center justify-between p-4 rounded-lg bg-muted">
              <div>
                <p className="text-label">Estimated CdA</p>
                <p className="text-metric">{result.cda.toFixed(3)} m²</p>
              </div>
              <span
                className={cn(
                  "px-3 py-1 text-sm font-medium rounded-full border",
                  CONFIDENCE_COLORS[result.confidence]
                )}
              >
                {result.confidence.charAt(0).toUpperCase() + result.confidence.slice(1)}
              </span>
            </div>

            {/* Confidence explanation */}
            <p className="text-caption">{CONFIDENCE_DESCRIPTIONS[result.confidence]}</p>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-metric-label">Activities</p>
                <p className="text-lg font-semibold">{result.n_activities_used}</p>
              </div>
              <div>
                <p className="text-metric-label">Segments</p>
                <p className="text-lg font-semibold">{result.n_segments_used}</p>
              </div>
              <div>
                <p className="text-metric-label">Duration</p>
                <p className="text-lg font-semibold">{formatDuration(result.total_duration_s)}</p>
              </div>
            </div>

            {/* Previous CdA comparison */}
            {result.previous_cda !== null && (
              <div className="text-sm text-body-secondary">
                Previous CdA: {result.previous_cda.toFixed(3)} m²
                {result.updated && (
                  <span className="ml-2 text-success">
                    (updated to {result.cda.toFixed(3)})
                  </span>
                )}
              </div>
            )}

            {/* Update status */}
            {result.updated ? (
              <div className="p-3 rounded-lg bg-success/10 text-success border border-success/20 text-sm">
                Bike CdA has been updated.
              </div>
            ) : (
              <div className="p-3 rounded-lg bg-warning/10 text-warning border border-warning/20 text-sm">
                Bike CdA was not updated (confidence below threshold).
              </div>
            )}

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div className="space-y-1">
                {result.warnings.map((warning, i) => (
                  <p key={i} className="text-caption text-warning">
                    {warning}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Error state */}
        {state === "error" && (
          <div className="py-4">
            <div className="p-4 rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
              <p className="font-medium">Calibration Failed</p>
              <p className="text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        <DialogFooter>
          {state === "config" && (
            <>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button onClick={handleCalibrate}>
                Run Calibration
              </Button>
            </>
          )}
          {state === "running" && (
            <Button variant="outline" onClick={handleClose}>
              Cancel
            </Button>
          )}
          {(state === "success" || state === "error") && (
            <Button onClick={handleClose}>
              {state === "success" ? "Done" : "Close"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
