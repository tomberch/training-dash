/**
 * Parameter Sliders Panel
 *
 * Adjustable sliders for real-time plan recalculation:
 * - FTP: ±50W from current
 * - Weight: ±10kg from current
 * - Target Intensity: 0.70 - 1.10
 * - CdA: ±0.05 from current
 *
 * Changes trigger debounced recalculation using client-side physics.
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import {
  recalculatePlan,
  formatTime,
  formatTimeDelta,
  type RiderParams as PhysicsRiderParams,
  type Segment,
  type PlanResult,
} from "@/lib/physics";
import type { RiderParams, BikeParams, SegmentTarget, CourseSegment } from "@/api/types";

// =============================================================================
// Types
// =============================================================================

export interface ParameterSlidersProps {
  /** Original plan rider parameters */
  riderParams: RiderParams;
  /** Original plan bike parameters */
  bikeParams: BikeParams;
  /** Original segment targets from the plan */
  segmentTargets: SegmentTarget[];
  /** Course segments for grade info */
  courseSegments: CourseSegment[];
  /** Original total time in seconds */
  originalTotalTimeS: number;
  /** Callback when parameters change (for live updates) */
  onRecalculate?: (result: PlanResult, params: UpdatedParams) => void;
  /** Callback when user wants to save changes */
  onSave?: (params: UpdatedParams) => void;
  /** Whether save is in progress */
  isSaving?: boolean;
  /** Additional class name */
  className?: string;
}

export interface UpdatedParams {
  ftpWatts: number;
  weightKg: number;
  targetIntensity: number;
  cda: number;
}

// =============================================================================
// Slider Component
// =============================================================================

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  formatValue: (value: number) => string;
  originalValue: number;
  unit?: string;
}

function SliderControl({
  label,
  value,
  min,
  max,
  step,
  onChange,
  formatValue,
  originalValue,
  unit,
}: SliderProps) {
  const delta = value - originalValue;
  const deltaStr = delta === 0 ? "" : delta > 0 ? `+${formatValue(delta)}` : formatValue(delta);
  const hasChanged = Math.abs(delta) > 0.001;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">{label}</Label>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium tabular-nums">
            {formatValue(value)}
            {unit && <span className="text-muted-foreground ml-0.5">{unit}</span>}
          </span>
          {hasChanged && (
            <span
              className={cn(
                "text-xs font-medium tabular-nums",
                delta > 0 ? "text-destructive" : "text-success"
              )}
            >
              ({deltaStr})
            </span>
          )}
        </div>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={([v]) => onChange(v)}
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{formatValue(min)}</span>
        <span>{formatValue(max)}</span>
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function ParameterSliders({
  riderParams,
  bikeParams,
  segmentTargets,
  courseSegments,
  originalTotalTimeS,
  onRecalculate,
  onSave,
  isSaving = false,
  className,
}: ParameterSlidersProps) {
  // Current slider values
  const [ftpWatts, setFtpWatts] = useState(riderParams.ftp_watts);
  const [weightKg, setWeightKg] = useState(riderParams.weight_kg);
  const [targetIntensity, setTargetIntensity] = useState(0.85); // Default, recalculated from plan
  const [cda, setCda] = useState(bikeParams.cda);

  // Recalculated result
  const [recalcResult, setRecalcResult] = useState<PlanResult | null>(null);

  // Slider ranges
  const ftpMin = Math.max(100, riderParams.ftp_watts - 50);
  const ftpMax = Math.min(500, riderParams.ftp_watts + 50);
  const weightMin = Math.max(40, riderParams.weight_kg - 10);
  const weightMax = Math.min(150, riderParams.weight_kg + 10);
  const cdaMin = Math.max(0.15, bikeParams.cda - 0.05);
  const cdaMax = Math.min(0.50, bikeParams.cda + 0.05);

  // Build segments with power targets for recalculation
  const segmentsWithPower = useMemo(() => {
    const targetMap = new Map<number, SegmentTarget>();
    for (const t of segmentTargets) {
      targetMap.set(t.segment_idx, t);
    }

    return courseSegments.map((seg, idx): Segment & { powerW: number } => {
      const target = targetMap.get(idx);
      return {
        segmentIdx: idx,
        distanceM: seg.distance_m,
        gradePct: seg.avg_grade_pct,
        powerW: target?.power_w ?? 200, // Default if missing
      };
    });
  }, [courseSegments, segmentTargets]);

  // Debounced recalculation
  useEffect(() => {
    const timer = setTimeout(() => {
      // Build physics rider params
      const bikeWeight = bikeParams.weight_kg ?? 8; // Default bike weight
      const physicsParams: PhysicsRiderParams = {
        massKg: weightKg + bikeWeight,
        cda: cda,
        crr: bikeParams.crr,
        efficiency: 0.97,
      };

      // Scale power targets based on FTP change and intensity
      const ftpRatio = ftpWatts / riderParams.ftp_watts;
      const scaledSegments = segmentsWithPower.map((seg) => ({
        ...seg,
        powerW: seg.powerW * ftpRatio * (targetIntensity / 0.85),
      }));

      const result = recalculatePlan(scaledSegments, physicsParams);
      setRecalcResult(result);

      if (onRecalculate) {
        onRecalculate(result, {
          ftpWatts,
          weightKg,
          targetIntensity,
          cda,
        });
      }
    }, 200); // 200ms debounce

    return () => clearTimeout(timer);
  }, [
    ftpWatts,
    weightKg,
    targetIntensity,
    cda,
    segmentsWithPower,
    bikeParams,
    riderParams.ftp_watts,
    onRecalculate,
  ]);

  // Check if any value has changed from original
  const hasChanges =
    Math.abs(ftpWatts - riderParams.ftp_watts) > 0.1 ||
    Math.abs(weightKg - riderParams.weight_kg) > 0.1 ||
    Math.abs(targetIntensity - 0.85) > 0.01 ||
    Math.abs(cda - bikeParams.cda) > 0.001;

  // Reset to original values
  const handleReset = useCallback(() => {
    setFtpWatts(riderParams.ftp_watts);
    setWeightKg(riderParams.weight_kg);
    setTargetIntensity(0.85);
    setCda(bikeParams.cda);
  }, [riderParams, bikeParams]);

  // Save changes
  const handleSave = useCallback(() => {
    if (onSave) {
      onSave({
        ftpWatts,
        weightKg,
        targetIntensity,
        cda,
      });
    }
  }, [onSave, ftpWatts, weightKg, targetIntensity, cda]);

  // Time delta from original
  const timeDelta = recalcResult ? recalcResult.totalTimeS - originalTotalTimeS : 0;

  return (
    <div className={cn("bg-card border border-border rounded-xl p-4", className)}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-card-title">Adjust Parameters</h2>
        {recalcResult && (
          <div className="text-right">
            <div className="text-lg font-semibold tabular-nums">
              {formatTime(recalcResult.totalTimeS)}
            </div>
            {hasChanges && (
              <div
                className={cn(
                  "text-sm font-medium tabular-nums",
                  timeDelta > 0 ? "text-destructive" : "text-success"
                )}
              >
                {formatTimeDelta(timeDelta)}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="space-y-6">
        {/* FTP Slider */}
        <SliderControl
          label="FTP"
          value={ftpWatts}
          min={ftpMin}
          max={ftpMax}
          step={1}
          onChange={setFtpWatts}
          formatValue={(v) => Math.round(v).toString()}
          originalValue={riderParams.ftp_watts}
          unit="W"
        />

        {/* Weight Slider */}
        <SliderControl
          label="Weight"
          value={weightKg}
          min={weightMin}
          max={weightMax}
          step={0.5}
          onChange={setWeightKg}
          formatValue={(v) => v.toFixed(1)}
          originalValue={riderParams.weight_kg}
          unit="kg"
        />

        {/* Target Intensity Slider */}
        <SliderControl
          label="Target Intensity"
          value={targetIntensity}
          min={0.7}
          max={1.1}
          step={0.01}
          onChange={setTargetIntensity}
          formatValue={(v) => `${Math.round(v * 100)}%`}
          originalValue={0.85}
        />

        {/* CdA Slider */}
        <SliderControl
          label="CdA"
          value={cda}
          min={cdaMin}
          max={cdaMax}
          step={0.001}
          onChange={setCda}
          formatValue={(v) => v.toFixed(3)}
          originalValue={bikeParams.cda}
          unit="m²"
        />
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2 mt-6">
        <Button
          variant="outline"
          size="sm"
          onClick={handleReset}
          disabled={!hasChanges || isSaving}
          className="flex-1"
        >
          Reset
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!hasChanges || isSaving}
          className="flex-1"
        >
          {isSaving ? "Saving..." : "Apply Changes"}
        </Button>
      </div>

      {/* Summary of changes */}
      {hasChanges && recalcResult && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="text-xs text-muted-foreground space-y-1">
            <div className="flex justify-between">
              <span>Avg Power:</span>
              <span className="font-medium">{Math.round(recalcResult.avgPowerW)} W</span>
            </div>
            <div className="flex justify-between">
              <span>Avg Speed:</span>
              <span className="font-medium">{(recalcResult.avgSpeedMps * 3.6).toFixed(1)} km/h</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
