/**
 * Activity Calc Lab Page
 *
 * Shows calculation trace for a single activity with expandable formulas
 * and what-if editing for thresholds.
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { fetchActivity, fetchWhatIf } from "@/api/activities";
import type { Activity, CalcTrace, WhatIfRequest } from "@/api/types";
import { calculateIntensityFactor, calculateTss } from "@/lib/training-load";
import { computePowerZones, computeHrZones, type ComputedZone } from "@/lib/zones";

// ============================================================================
// HOOK: useCalcLab
// ============================================================================

interface UseCalcLabResult {
  activity: Activity | null;
  originalTrace: CalcTrace | null;
  currentTrace: CalcTrace | null;
  whatIfParams: WhatIfRequest;
  isLoading: boolean;
  isRecalculating: boolean;
  error: string | null;
  setWhatIfParam: (key: keyof WhatIfRequest, value: number | null) => void;
  resetAll: () => void;
  hasChanges: boolean;
}

function useCalcLab(activityId: string | undefined): UseCalcLabResult {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [originalTrace, setOriginalTrace] = useState<CalcTrace | null>(null);
  const [currentTrace, setCurrentTrace] = useState<CalcTrace | null>(null);
  const [whatIfParams, setWhatIfParams] = useState<WhatIfRequest>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load activity with calc_trace on mount
  useEffect(() => {
    if (!activityId) return;

    setIsLoading(true);
    setError(null);

    fetchActivity(activityId, "calc_trace")
      .then((data) => {
        setActivity(data);
        setOriginalTrace(data.calc_trace ?? null);
        setCurrentTrace(data.calc_trace ?? null);
      })
      .catch((err) => {
        setError(err.message || "Failed to load activity");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [activityId]);

  // Debounced what-if recalculation
  useEffect(() => {
    if (!activityId || !activity) return;

    const hasWhatIfParams = Object.values(whatIfParams).some((v) => v != null);
    if (!hasWhatIfParams) {
      // Reset to original trace when no what-if params
      setCurrentTrace(originalTrace);
      return;
    }

    const timer = setTimeout(async () => {
      setIsRecalculating(true);
      try {
        const result = await fetchWhatIf(activityId, whatIfParams);
        setCurrentTrace(result.calc_trace);
      } catch (err) {
        console.error("What-if calculation failed:", err);
        // Keep current trace on error
      } finally {
        setIsRecalculating(false);
      }
    }, 300); // 300ms debounce

    return () => clearTimeout(timer);
  }, [activityId, activity, whatIfParams, originalTrace]);

  const setWhatIfParam = useCallback((key: keyof WhatIfRequest, value: number | null) => {
    setWhatIfParams((prev) => ({
      ...prev,
      [key]: value,
    }));
  }, []);

  const resetAll = useCallback(() => {
    setWhatIfParams({});
    setCurrentTrace(originalTrace);
  }, [originalTrace]);

  const hasChanges = Object.values(whatIfParams).some((v) => v != null);

  return {
    activity,
    originalTrace,
    currentTrace,
    whatIfParams,
    isLoading,
    isRecalculating,
    error,
    setWhatIfParam,
    resetAll,
    hasChanges,
  };
}

// ============================================================================
// COMPONENTS
// ============================================================================

function InfoTooltip({ explanation }: { explanation: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-muted text-muted-foreground text-xs hover:bg-muted/80 ml-1">
            ?
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-sm">{explanation}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface ExpandableFormulaProps {
  label: string;
  formula: string;
  result: number | string;
  unit?: string;
  originalResult?: number | string;
  explanation: string;
  substituted?: string;
  isLoading?: boolean;
  onRestore?: () => void;
}

function ExpandableFormula({
  label,
  formula,
  result,
  unit,
  originalResult,
  explanation,
  substituted,
  isLoading = false,
  onRestore,
}: ExpandableFormulaProps) {
  const [expanded, setExpanded] = useState(false);
  const hasChanged = originalResult !== undefined && result !== originalResult;

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors text-left"
      >
        <div className="flex items-center gap-4 min-w-0">
          <span className="font-medium">{label}</span>
          <code className="text-sm text-muted-foreground bg-muted px-2 py-0.5 rounded truncate">
            {formula}
          </code>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={cn("text-lg font-semibold tabular-nums", isLoading && "opacity-50")}>
            {typeof result === "number" ? result.toFixed(1) : result}
            {unit && <span className="text-sm font-normal ml-0.5">{unit}</span>}
          </span>
          {hasChanged && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRestore?.();
              }}
              className="text-xs text-muted-foreground hover:text-foreground underline"
            >
              (was {typeof originalResult === "number" ? originalResult.toFixed(1) : originalResult})
            </button>
          )}
          <svg
            className={cn("w-5 h-5 transition-transform text-muted-foreground", expanded && "rotate-180")}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      {expanded && (
        <div className="p-4 border-t border-border bg-muted/30 space-y-2">
          <p className="text-sm text-muted-foreground">{explanation}</p>
          {substituted && (
            <code className="text-xs bg-muted p-2 rounded block font-mono">{substituted}</code>
          )}
        </div>
      )}
    </div>
  );
}

interface InputFieldProps {
  label: string;
  explanation: string;
  value: number | null;
  originalValue: number | null;
  unit: string;
  min: number;
  max: number;
  onChange: (value: number | null) => void;
  onRestore: () => void;
}

function InputField({
  label,
  explanation,
  value,
  originalValue,
  unit,
  min,
  max,
  onChange,
  onRestore,
}: InputFieldProps) {
  const displayValue = value ?? originalValue ?? "";
  const hasChanged = value !== null && value !== originalValue;

  return (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-b-0">
      <div className="flex items-center">
        <Label className="font-medium">{label}</Label>
        <InfoTooltip explanation={explanation} />
      </div>
      <div className="flex items-center gap-2">
        <Input
          type="number"
          value={displayValue}
          min={min}
          max={max}
          onChange={(e) => {
            const v = e.target.value ? Number(e.target.value) : null;
            onChange(v);
          }}
          className="w-24 text-right"
        />
        <span className="text-muted-foreground w-8">{unit}</span>
        {hasChanged && (
          <button onClick={onRestore} className="text-xs text-muted-foreground hover:text-foreground underline">
            (was {originalValue})
          </button>
        )}
      </div>
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-3 py-4 mt-4 first:mt-0">
      <div className="h-px flex-1 bg-border" />
      <span className="text-section-heading text-muted-foreground">{title}</span>
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}

function ZonesGrid({
  zones,
  originalZones,
  label,
  unitLabel,
}: {
  zones: ComputedZone[] | null;
  originalZones: ComputedZone[] | null;
  label: string;
  unitLabel: string;
}) {
  if (!zones) {
    return (
      <div className="py-3 text-muted-foreground text-sm">
        No {label.toLowerCase()} available (threshold not set)
      </div>
    );
  }

  return (
    <div className="py-3">
      <div className="flex items-center mb-3">
        <span className="font-medium">{label}</span>
        <InfoTooltip explanation={`Zone boundaries calculated from your threshold. Each zone targets a specific training adaptation.`} />
      </div>
      <div className="grid grid-cols-7 gap-2 text-center text-sm">
        {zones.map((z, i) => {
          const orig = originalZones?.[i];
          const minVal = z.minValue;
          const maxVal = z.maxValue;
          const origMin = orig?.minValue ?? minVal;
          const origMax = orig?.maxValue ?? maxVal;
          const hasChanged = minVal !== origMin || maxVal !== origMax;

          return (
            <div
              key={z.zone}
              className={cn("p-2 rounded bg-muted/50", hasChanged && "ring-1 ring-primary/50")}
            >
              <div className="font-medium">Z{z.zone}</div>
              <div className="text-xs text-muted-foreground">
                {minVal}-{maxVal ?? "∞"}
                {unitLabel}
              </div>
              {hasChanged && (
                <div className="text-xs text-muted-foreground">
                  (was {origMin}-{origMax ?? "∞"})
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ZoneTimesGrid({
  zoneTimes,
  label,
}: {
  zoneTimes: Record<number, number> | null;
  label: string;
}) {
  if (!zoneTimes) return null;

  return (
    <div className="py-3 border-t border-border">
      <div className="flex items-center mb-3">
        <span className="font-medium">Time in {label}</span>
        <InfoTooltip explanation="Time spent in each zone during this activity." />
      </div>
      <div className="grid grid-cols-7 gap-2 text-center text-sm">
        {Object.entries(zoneTimes).map(([zone, seconds]) => (
          <div key={zone} className="p-2 rounded bg-muted/50">
            <div className="font-medium">Z{zone}</div>
            <div className="text-xs text-muted-foreground">{Math.floor(seconds / 60)}m</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PeaksGrid({ peaks }: { peaks: Activity["peaks"] }) {
  if (!peaks || peaks.length === 0) {
    return <div className="py-3 text-muted-foreground text-sm">No peak power data available</div>;
  }

  return (
    <div className="py-3">
      <div className="flex items-center mb-3">
        <span className="font-medium">Best Average Power at Duration</span>
        <InfoTooltip explanation="Maximum average power sustained for each duration. Used for power curve analysis." />
      </div>
      <div className="grid grid-cols-4 gap-3 text-sm">
        {peaks.map((peak) => {
          const dur = peak.duration_seconds;
          const label = dur < 60 ? `${dur}s` : dur < 3600 ? `${Math.floor(dur / 60)}m` : `${Math.floor(dur / 3600)}h`;
          return (
            <div key={dur} className="p-2 rounded bg-muted/50 text-center">
              <div className="font-medium">{peak.watts}W</div>
              <div className="text-xs text-muted-foreground">{label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-64" />
      <div className="space-y-3 mt-6">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export function CalcLabPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    activity,
    currentTrace,
    whatIfParams,
    isLoading,
    isRecalculating,
    error,
    setWhatIfParam,
    resetAll,
    hasChanges,
  } = useCalcLab(id);

  // Compute client-side values
  const computedValues = useMemo(() => {
    if (!activity) return null;

    const ftp = whatIfParams.ftp ?? activity.effective_ftp;
    const lthr = whatIfParams.lthr ?? activity.effective_lthr;
    const np = activity.np_power_w;
    const duration = activity.moving_time_s;

    const originalFtp = activity.effective_ftp;
    const originalIf = originalFtp && np ? calculateIntensityFactor(np, originalFtp) : null;
    const originalTss = originalFtp && np ? calculateTss({
      normalizedPower: np,
      ftp: originalFtp,
      durationSeconds: duration,
    }) : null;

    const currentIf = ftp && np ? calculateIntensityFactor(np, ftp) : null;
    const currentTss = ftp && np ? calculateTss({
      normalizedPower: np,
      ftp,
      durationSeconds: duration,
    }) : null;

    // Client-side zone computation for display
    const currentPowerZones = ftp ? computePowerZones(ftp) : null;
    const currentHrZones = lthr ? computeHrZones(lthr) : null;
    const originalPowerZones = originalFtp ? computePowerZones(originalFtp) : null;
    const originalHrZones = activity.effective_lthr ? computeHrZones(activity.effective_lthr) : null;

    return {
      np,
      duration,
      ftp,
      lthr,
      originalFtp,
      originalLthr: activity.effective_lthr,
      currentIf,
      originalIf,
      currentTss,
      originalTss,
      currentPowerZones,
      originalPowerZones,
      currentHrZones,
      originalHrZones,
    };
  }, [activity, whatIfParams]);

  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <LoadingSkeleton />
      </div>
    );
  }

  if (error || !activity) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="text-center py-12">
          <h1 className="text-page-title mb-2">Error</h1>
          <p className="text-muted-foreground mb-4">{error || "Activity not found"}</p>
          <Button variant="outline" onClick={() => navigate(-1)}>
            Go Back
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              to={`/activities/${id}`}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              &larr; Back to Activity
            </Link>
          </div>
          <h1 className="text-page-title">Calc Lab</h1>
          <p className="text-page-subtitle">
            {activity.title || "Untitled Activity"} &bull;{" "}
            {new Date(activity.started_at).toLocaleDateString()}
          </p>
        </div>
        {hasChanges && (
          <Button variant="outline" size="sm" onClick={resetAll}>
            Reset All
          </Button>
        )}
      </div>

      {/* Main content */}
      <div className={cn("space-y-3", isRecalculating && "opacity-70 transition-opacity")}>
        {/* INPUTS SECTION */}
        <SectionHeader title="Inputs (Thresholds at Activity Time)" />

        <div className="border border-border rounded-lg p-4">
          <InputField
            label="FTP"
            explanation="Functional Threshold Power — the highest power you can sustain for approximately one hour."
            value={whatIfParams.ftp ?? null}
            originalValue={activity.effective_ftp}
            unit="W"
            min={50}
            max={500}
            onChange={(v) => setWhatIfParam("ftp", v)}
            onRestore={() => setWhatIfParam("ftp", null)}
          />
          <InputField
            label="LTHR"
            explanation="Lactate Threshold Heart Rate — the heart rate at which lactate accumulates faster than it can be cleared."
            value={whatIfParams.lthr ?? null}
            originalValue={activity.effective_lthr}
            unit="bpm"
            min={100}
            max={220}
            onChange={(v) => setWhatIfParam("lthr", v)}
            onRestore={() => setWhatIfParam("lthr", null)}
          />
        </div>

        {/* TRAINING LOAD SECTION */}
        <SectionHeader title="Training Load" />

        <ExpandableFormula
          label="Normalized Power (NP)"
          formula="⁴√(mean(30s_avg⁴))"
          result={activity.np_power_w ?? 0}
          unit="W"
          explanation="Accounts for the variability of power output. The 30-second rolling average raised to the 4th power emphasizes hard efforts."
          substituted={`Server-calculated from ${activity.moving_time_s}s of power data`}
        />

        {computedValues && (
          <>
            <ExpandableFormula
              label="Intensity Factor (IF)"
              formula="NP / FTP"
              result={computedValues.currentIf ?? 0}
              originalResult={
                whatIfParams.ftp != null ? computedValues.originalIf ?? undefined : undefined
              }
              explanation="How hard the ride was relative to your threshold. IF of 1.0 means you rode at exactly your FTP."
              substituted={`= ${computedValues.np} / ${computedValues.ftp} = ${(computedValues.currentIf ?? 0).toFixed(3)}`}
              isLoading={isRecalculating}
              onRestore={() => setWhatIfParam("ftp", null)}
            />

            <ExpandableFormula
              label="Training Stress Score (TSS)"
              formula="(t × NP × IF) / (FTP × 3600) × 100"
              result={computedValues.currentTss ?? 0}
              originalResult={
                whatIfParams.ftp != null ? computedValues.originalTss ?? undefined : undefined
              }
              explanation="Quantifies training load. 100 TSS is roughly equivalent to riding at FTP for one hour."
              substituted={`= (${computedValues.duration} × ${computedValues.np} × ${(computedValues.currentIf ?? 0).toFixed(3)}) / (${computedValues.ftp} × 3600) × 100`}
              isLoading={isRecalculating}
              onRestore={() => setWhatIfParam("ftp", null)}
            />
          </>
        )}

        {/* POWER ZONES SECTION */}
        <SectionHeader title="Power Zones" />

        <div className="border border-border rounded-lg p-4">
          <ZonesGrid
            zones={computedValues?.currentPowerZones ?? null}
            originalZones={whatIfParams.ftp != null ? computedValues?.originalPowerZones ?? null : null}
            label="Zone Boundaries"
            unitLabel="W"
          />
          <ZoneTimesGrid
            zoneTimes={currentTrace?.power_zone_times ?? null}
            label="Power Zones"
          />
        </div>

        {/* HR ZONES SECTION */}
        <SectionHeader title="HR Zones" />

        <div className="border border-border rounded-lg p-4">
          <ZonesGrid
            zones={computedValues?.currentHrZones ?? null}
            originalZones={whatIfParams.lthr != null ? computedValues?.originalHrZones ?? null : null}
            label="Zone Boundaries"
            unitLabel="bpm"
          />
          <ZoneTimesGrid
            zoneTimes={currentTrace?.hr_zone_times ?? null}
            label="HR Zones"
          />
        </div>

        {/* PEAKS SECTION */}
        <SectionHeader title="Peak Powers" />

        <div className="border border-border rounded-lg p-4">
          <PeaksGrid peaks={activity.peaks} />
        </div>

        {/* W'BAL SECTION */}
        <SectionHeader title="W'bal Analysis" />

        <div className="border border-border rounded-lg p-4 space-y-3">
          {currentTrace?.w_prime_joules && currentTrace?.cp_watts ? (
            <>
              <div className="flex items-center justify-between py-2">
                <div className="flex items-center">
                  <span className="font-medium">CP</span>
                  <InfoTooltip explanation="Critical Power — the boundary between sustainable and unsustainable exercise." />
                </div>
                <span className="font-semibold">{currentTrace.cp_watts}W</span>
              </div>
              <div className="flex items-center justify-between py-2 border-t border-border">
                <div className="flex items-center">
                  <span className="font-medium">W'</span>
                  <InfoTooltip explanation="W' (W-prime) — your anaerobic work capacity above CP." />
                </div>
                <span className="font-semibold">{(currentTrace.w_prime_joules / 1000).toFixed(1)}kJ</span>
              </div>
              {activity.wbal_min_joules != null && (
                <div className="flex items-center justify-between py-2 border-t border-border">
                  <div className="flex items-center">
                    <span className="font-medium">Minimum W'bal</span>
                    <InfoTooltip explanation="The lowest point of your W' balance during the ride. Lower = closer to exhaustion." />
                  </div>
                  <span className="font-semibold">
                    {(activity.wbal_min_joules / 1000).toFixed(1)}kJ ({activity.wbal_min_pct}%)
                  </span>
                </div>
              )}
              {currentTrace.wbal_curve && currentTrace.wbal_curve.length > 0 && (
                <div className="pt-2 border-t border-border">
                  <p className="text-sm text-muted-foreground">
                    W'bal curve: {currentTrace.wbal_curve.length} sample points
                    (chart visualization coming soon)
                  </p>
                </div>
              )}
            </>
          ) : (
            <p className="text-muted-foreground text-sm py-2">
              W'bal data not available (requires FTP/CP threshold)
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
