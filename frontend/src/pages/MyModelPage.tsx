/**
 * My Model Page (Calc Lab General Overview)
 *
 * Shows athlete model parameters with simulator for what-if calculations:
 * - Simulator: power/speed/time calculator
 * - Thresholds: FTP, LTHR with history
 * - Power Model: CP, W' from power curve fitting
 * - Bike Parameters: CdA, Crr, weight per bike
 * - Current Fitness: CTL, ATL, TSB
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
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
import {
  fetchThresholds,
  fetchPMC,
  fetchFitness,
  type ThresholdEntry,
  type PMCPoint,
  type FitnessResponse,
} from "@/api";
import { fetchBikes } from "@/api/bikes";
import type { Bike } from "@/api/types";
import { powerRequired, speedFromPower, formatTime } from "@/lib/physics";

// ============================================================================
// TYPES
// ============================================================================

type SolveFor = "power" | "speed" | "time";

interface SimulatorInputs {
  power: number;
  speedKph: number;
  distanceKm: number;
  gradePct: number;
  massKg: number;
  cda: number;
  crr: number;
  windKph: number;
}

// ============================================================================
// HELPER COMPONENTS
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

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-3 py-4 mt-6 first:mt-0">
      <div className="h-px flex-1 bg-border" />
      <span className="text-section-heading text-muted-foreground">{title}</span>
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}

function MetricCard({
  label,
  value,
  unit,
  subtext,
  tooltip,
}: {
  label: string;
  value: string | number | null;
  unit?: string;
  subtext?: string;
  tooltip?: string;
}) {
  return (
    <div className="p-4 rounded-lg bg-muted/50">
      <div className="flex items-center mb-1">
        <span className="text-metric-label">{label}</span>
        {tooltip && <InfoTooltip explanation={tooltip} />}
      </div>
      <div className="text-2xl font-bold tabular-nums">
        {value ?? "—"}
        {unit && value !== null && (
          <span className="text-base font-normal text-muted-foreground ml-1">{unit}</span>
        )}
      </div>
      {subtext && <p className="text-caption mt-1">{subtext}</p>}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-64" />
      <div className="grid grid-cols-2 gap-4 mt-6">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    </div>
  );
}

// ============================================================================
// SIMULATOR COMPONENT
// ============================================================================

interface SimulatorProps {
  defaultMassKg: number;
  defaultCda: number;
  defaultCrr: number;
  bikes: Bike[];
}

function Simulator({ defaultMassKg, defaultCda, defaultCrr, bikes }: SimulatorProps) {
  const [solveFor, setSolveFor] = useState<SolveFor>("speed");
  const [selectedBikeId, setSelectedBikeId] = useState<string>("custom");
  const [inputs, setInputs] = useState<SimulatorInputs>({
    power: 200,
    speedKph: 30,
    distanceKm: 40,
    gradePct: 0,
    massKg: defaultMassKg,
    cda: defaultCda,
    crr: defaultCrr,
    windKph: 0,
  });

  // Update mass/cda/crr when bike is selected
  useEffect(() => {
    if (selectedBikeId === "custom") return;
    const bike = bikes.find((b) => b.id.toString() === selectedBikeId);
    if (bike) {
      setInputs((prev) => ({
        ...prev,
        cda: bike.cda ?? defaultCda,
        crr: bike.crr ?? defaultCrr,
        massKg: prev.massKg, // Keep rider mass, just update bike params
      }));
    }
  }, [selectedBikeId, bikes, defaultCda, defaultCrr]);

  const updateInput = (key: keyof SimulatorInputs, value: number) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
  };

  // Calculate result based on what we're solving for
  const result = useMemo(() => {
    const riderParams = {
      massKg: inputs.massKg,
      cda: inputs.cda,
      crr: inputs.crr,
    };
    const env = {
      windSpeedMps: inputs.windKph / 3.6, // Convert km/h to m/s
    };

    try {
      switch (solveFor) {
        case "speed": {
          const speedMps = speedFromPower(inputs.power, inputs.gradePct, riderParams, env);
          const speedKph = speedMps * 3.6;
          const timeS = (inputs.distanceKm * 1000) / speedMps;
          return { speedKph, timeS, power: inputs.power };
        }
        case "power": {
          const speedMps = inputs.speedKph / 3.6;
          const power = powerRequired(speedMps, inputs.gradePct, riderParams, env);
          const timeS = (inputs.distanceKm * 1000) / speedMps;
          return { speedKph: inputs.speedKph, timeS, power };
        }
        case "time": {
          // Given speed, calculate time for distance
          const speedMps = inputs.speedKph / 3.6;
          const power = powerRequired(speedMps, inputs.gradePct, riderParams, env);
          const timeS = (inputs.distanceKm * 1000) / speedMps;
          return { speedKph: inputs.speedKph, timeS, power };
        }
      }
    } catch {
      return null;
    }
  }, [inputs, solveFor]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Power/Speed Calculator
          <InfoTooltip explanation="Calculate power, speed, or time based on your parameters. Uses cycling physics model with aero and rolling resistance." />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Solve For Selection */}
        <div className="flex items-center gap-4">
          <Label>Solve for:</Label>
          <div className="flex gap-2">
            {(["speed", "power", "time"] as SolveFor[]).map((option) => (
              <Button
                key={option}
                variant={solveFor === option ? "default" : "outline"}
                size="sm"
                onClick={() => setSolveFor(option)}
              >
                {option.charAt(0).toUpperCase() + option.slice(1)}
              </Button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Input Column */}
          <div className="space-y-4">
            <h4 className="font-medium text-sm text-muted-foreground">Inputs</h4>

            {/* Power (disabled when solving for power) */}
            <div className="space-y-1.5">
              <Label htmlFor="sim-power">Power</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="sim-power"
                  type="number"
                  value={inputs.power}
                  onChange={(e) => updateInput("power", Number(e.target.value))}
                  disabled={solveFor === "power"}
                  className={cn("w-24", solveFor === "power" && "opacity-50")}
                />
                <span className="text-muted-foreground">W</span>
              </div>
            </div>

            {/* Speed (disabled when solving for speed) */}
            <div className="space-y-1.5">
              <Label htmlFor="sim-speed">Speed</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="sim-speed"
                  type="number"
                  value={inputs.speedKph}
                  onChange={(e) => updateInput("speedKph", Number(e.target.value))}
                  disabled={solveFor === "speed"}
                  className={cn("w-24", solveFor === "speed" && "opacity-50")}
                />
                <span className="text-muted-foreground">km/h</span>
              </div>
            </div>

            {/* Distance */}
            <div className="space-y-1.5">
              <Label htmlFor="sim-distance">Distance</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="sim-distance"
                  type="number"
                  value={inputs.distanceKm}
                  onChange={(e) => updateInput("distanceKm", Number(e.target.value))}
                  className="w-24"
                />
                <span className="text-muted-foreground">km</span>
              </div>
            </div>

            {/* Gradient */}
            <div className="space-y-1.5">
              <Label htmlFor="sim-grade">Gradient</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="sim-grade"
                  type="number"
                  value={inputs.gradePct}
                  onChange={(e) => updateInput("gradePct", Number(e.target.value))}
                  className="w-24"
                  step="0.5"
                />
                <span className="text-muted-foreground">%</span>
              </div>
            </div>

            {/* Wind */}
            <div className="space-y-1.5">
              <Label htmlFor="sim-wind">Headwind (+) / Tailwind (-)</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="sim-wind"
                  type="number"
                  value={inputs.windKph}
                  onChange={(e) => updateInput("windKph", Number(e.target.value))}
                  className="w-24"
                />
                <span className="text-muted-foreground">km/h</span>
              </div>
            </div>
          </div>

          {/* Parameters Column */}
          <div className="space-y-4">
            <h4 className="font-medium text-sm text-muted-foreground">Parameters</h4>

            {/* Bike Selection */}
            {bikes.length > 0 && (
              <div className="space-y-1.5">
                <Label htmlFor="sim-bike">Bike</Label>
                <select
                  id="sim-bike"
                  value={selectedBikeId}
                  onChange={(e) => setSelectedBikeId(e.target.value)}
                  className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="custom">Custom</option>
                  {bikes.map((bike) => (
                    <option key={bike.id} value={bike.id.toString()}>
                      {bike.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Total Mass */}
            <div className="space-y-1.5">
              <Label htmlFor="sim-mass">Total Mass (rider + bike)</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="sim-mass"
                  type="number"
                  value={inputs.massKg}
                  onChange={(e) => updateInput("massKg", Number(e.target.value))}
                  className="w-24"
                  step="0.5"
                />
                <span className="text-muted-foreground">kg</span>
              </div>
            </div>

            {/* CdA */}
            <div className="space-y-1.5">
              <Label htmlFor="sim-cda">CdA</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="sim-cda"
                  type="number"
                  value={inputs.cda}
                  onChange={(e) => updateInput("cda", Number(e.target.value))}
                  className="w-24"
                  step="0.01"
                />
                <span className="text-muted-foreground">m²</span>
              </div>
            </div>

            {/* Crr */}
            <div className="space-y-1.5">
              <Label htmlFor="sim-crr">Crr</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="sim-crr"
                  type="number"
                  value={inputs.crr}
                  onChange={(e) => updateInput("crr", Number(e.target.value))}
                  className="w-24"
                  step="0.001"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Result */}
        <div className="p-4 rounded-lg bg-primary/10 border border-primary/20">
          <h4 className="font-medium mb-3">Result</h4>
          {result ? (
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className={cn(solveFor === "power" && "ring-2 ring-primary rounded-lg p-2")}>
                <p className="text-caption">Power</p>
                <p className="text-xl font-bold">{Math.round(result.power)}W</p>
              </div>
              <div className={cn(solveFor === "speed" && "ring-2 ring-primary rounded-lg p-2")}>
                <p className="text-caption">Speed</p>
                <p className="text-xl font-bold">{result.speedKph.toFixed(1)} km/h</p>
              </div>
              <div className={cn(solveFor === "time" && "ring-2 ring-primary rounded-lg p-2")}>
                <p className="text-caption">Time</p>
                <p className="text-xl font-bold">{formatTime(result.timeS)}</p>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground text-center">Unable to calculate</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export function MyModelPage() {
  const [loading, setLoading] = useState(true);
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [pmc, setPmc] = useState<PMCPoint[]>([]);
  const [fitness, setFitness] = useState<FitnessResponse | null>(null);
  const [bikes, setBikes] = useState<Bike[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Load all data on mount
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [thresholdsData, pmcData, fitnessData, bikesData] = await Promise.all([
        fetchThresholds(),
        fetchPMC(),
        fetchFitness(),
        fetchBikes(),
      ]);
      setThresholds(thresholdsData);
      setPmc(pmcData);
      setFitness(fitnessData);
      setBikes(bikesData);
    } catch (err) {
      console.error("Failed to load model data:", err);
      setError("Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Get current threshold values
  const currentThreshold = useMemo(() => {
    if (thresholds.length === 0) return null;
    // Sort by date descending and get the most recent
    const sorted = [...thresholds].sort(
      (a, b) => new Date(b.effective_date).getTime() - new Date(a.effective_date).getTime()
    );
    return sorted[0];
  }, [thresholds]);

  // Get current PMC values (most recent)
  const currentPmc = useMemo(() => {
    if (pmc.length === 0) return null;
    const sorted = [...pmc].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    );
    return sorted[0];
  }, [pmc]);

  // Get current power model (CP, W')
  const currentPowerModel = useMemo(() => {
    if (!fitness?.current) return null;
    return fitness.current;
  }, [fitness]);

  // Default bike for simulator
  const defaultBike = useMemo(() => {
    const def = bikes.find((b) => b.is_default);
    return def || bikes[0];
  }, [bikes]);

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (error) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="text-center py-12">
          <h1 className="text-page-title mb-2">Error</h1>
          <p className="text-muted-foreground mb-4">{error}</p>
          <Button variant="outline" onClick={loadData}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // Defaults for simulator
  const defaultMassKg = 75; // Rider + bike typical default
  const defaultCda = defaultBike?.cda ?? 0.32;
  const defaultCrr = defaultBike?.crr ?? 0.005;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-page-title">My Model</h1>
        <p className="text-page-subtitle">
          Your athlete parameters and calculation simulator
        </p>
      </div>

      {/* Simulator (prominent at top) */}
      <Simulator
        defaultMassKg={defaultMassKg}
        defaultCda={defaultCda}
        defaultCrr={defaultCrr}
        bikes={bikes}
      />

      {/* Thresholds */}
      <SectionHeader title="Thresholds" />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          label="FTP"
          value={currentThreshold?.ftp_watts ?? null}
          unit="W"
          subtext={
            currentThreshold?.effective_date
              ? `since ${new Date(currentThreshold.effective_date).toLocaleDateString()}`
              : undefined
          }
          tooltip="Functional Threshold Power - the highest power you can sustain for ~1 hour"
        />
        <MetricCard
          label="LTHR"
          value={currentThreshold?.lthr_bpm ?? null}
          unit="bpm"
          subtext={
            currentThreshold?.effective_date
              ? `since ${new Date(currentThreshold.effective_date).toLocaleDateString()}`
              : undefined
          }
          tooltip="Lactate Threshold Heart Rate - heart rate at lactate threshold"
        />
        <MetricCard
          label="HRmax"
          value={currentThreshold?.hrmax_bpm ?? null}
          unit="bpm"
          tooltip="Maximum heart rate"
        />
      </div>

      <div className="mt-2 text-right">
        <Link
          to="/athlete?tab=thresholds"
          className="text-sm text-primary hover:underline"
        >
          View threshold history →
        </Link>
      </div>

      {/* Power Model */}
      <SectionHeader title="Power Model" />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          label="Critical Power (CP)"
          value={currentPowerModel?.cp_watts ?? null}
          unit="W"
          tooltip="The boundary between sustainable and unsustainable exercise intensity"
        />
        <MetricCard
          label="W' (W-prime)"
          value={
            currentPowerModel?.w_prime_joules
              ? (currentPowerModel.w_prime_joules / 1000).toFixed(1)
              : null
          }
          unit="kJ"
          tooltip="Anaerobic work capacity - the amount of work you can do above CP before exhaustion"
        />
        <MetricCard
          label="Peak Power"
          value={currentPowerModel?.pp_watts ?? null}
          unit="W"
          tooltip="Maximum instantaneous power from power curve fit"
        />
      </div>

      {currentPowerModel && (
        <div className="mt-2 text-right">
          <span className="text-caption">
            Computed {new Date(currentPowerModel.computed_at).toLocaleDateString()}
          </span>
        </div>
      )}

      {/* Bike Parameters */}
      <SectionHeader title="Bike Parameters" />

      {bikes.length === 0 ? (
        <div className="p-8 text-center border border-dashed border-border rounded-lg">
          <p className="text-muted-foreground mb-3">No bikes configured</p>
          <Link to="/gear">
            <Button variant="outline" size="sm">
              Add Bike
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {bikes.slice(0, 4).map((bike) => (
            <Card key={bike.id} className={cn(bike.is_default && "ring-1 ring-primary")}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-medium">{bike.name}</span>
                  {bike.is_default && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-primary/20 text-primary">
                      Default
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-caption">Weight</p>
                    <p className="font-medium">
                      {bike.weight_kg ? `${bike.weight_kg} kg` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-caption">CdA</p>
                    <p className="font-medium">
                      {bike.cda ? bike.cda.toFixed(3) : "—"} m²
                    </p>
                    {bike.cda_source && (
                      <p className="text-xs text-muted-foreground">{bike.cda_source}</p>
                    )}
                  </div>
                  <div>
                    <p className="text-caption">Crr</p>
                    <p className="font-medium">
                      {bike.crr ? bike.crr.toFixed(4) : "—"}
                    </p>
                    {bike.crr_source && (
                      <p className="text-xs text-muted-foreground">{bike.crr_source}</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {bikes.length > 0 && (
        <div className="mt-2 text-right">
          <Link to="/gear" className="text-sm text-primary hover:underline">
            Manage bikes →
          </Link>
        </div>
      )}

      {/* Current Fitness */}
      <SectionHeader title="Current Fitness" />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          label="CTL (Fitness)"
          value={currentPmc?.ctl != null ? Math.round(currentPmc.ctl) : null}
          tooltip="Chronic Training Load - your long-term training load, representing fitness"
        />
        <MetricCard
          label="ATL (Fatigue)"
          value={currentPmc?.atl != null ? Math.round(currentPmc.atl) : null}
          tooltip="Acute Training Load - your short-term training load, representing fatigue"
        />
        <MetricCard
          label="TSB (Form)"
          value={currentPmc?.tsb != null ? Math.round(currentPmc.tsb) : null}
          subtext={
            currentPmc?.tsb != null
              ? currentPmc.tsb > 5
                ? "Fresh"
                : currentPmc.tsb < -10
                  ? "Fatigued"
                  : "Neutral"
              : undefined
          }
          tooltip="Training Stress Balance - the difference between CTL and ATL, indicating freshness"
        />
      </div>

      {currentPmc && (
        <div className="mt-2 text-right">
          <Link to="/pmc" className="text-sm text-primary hover:underline">
            View PMC chart →
          </Link>
        </div>
      )}

      {/* Info footer */}
      <div className="mt-8 p-4 rounded-lg bg-muted/50 border border-border text-sm">
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">About this page</span>{" "}
          Your model parameters are used to calculate training metrics and make race predictions.
          The simulator uses the Martin et al. (1998) cycling power equation.{" "}
          <Link
            to="/activities"
            className="text-primary hover:underline"
          >
            View activity Calc Lab
          </Link>{" "}
          for per-activity calculation breakdown.
        </p>
      </div>
    </div>
  );
}
