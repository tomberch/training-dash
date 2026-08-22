import * as React from "react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

interface MetricGroupCardProps {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}

export function MetricGroupCard({ icon, title, children }: MetricGroupCardProps) {
  return (
    <div className="bg-card rounded-xl border border-border p-5 card-hover transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h3 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">{title}</h3>
      </div>
      <div className="space-y-3">
        {children}
      </div>
    </div>
  );
}

interface MetricEntryProps {
  label: string;
  value: string;
  subtitle?: string;
  tooltip?: string;
  valueClass?: string;
  prominent?: boolean;
}

export function MetricEntry({ 
  label, 
  value, 
  subtitle,
  tooltip,
  valueClass,
  prominent 
}: MetricEntryProps) {
  const content = (
    <div className="flex justify-between items-baseline">
      <span className="text-muted-foreground text-sm">{label}</span>
      <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
        {value}
      </span>
    </div>
  );

  const withSubtitle = subtitle ? (
    <div className="flex justify-between items-baseline">
      <span className="text-muted-foreground text-sm">{label}</span>
      <div className="text-right">
        <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
          {value}
        </span>
        {subtitle && (
          <div className="text-xs text-primary">{subtitle}</div>
        )}
      </div>
    </div>
  ) : content;

  if (tooltip) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="cursor-help flex justify-between items-baseline">
            <span className="text-muted-foreground text-sm flex items-center gap-1">
              {label}
              <svg className="w-3 h-3 text-muted-foreground" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </span>
            <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
              {value}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {tooltip}
        </TooltipContent>
      </Tooltip>
    );
  }

  return withSubtitle;
}


// --- Aero Estimation Card ---

interface AeroEstimateCardProps {
  estimatedCda: number | null;
  estimatedCrr: number | null;
  aeroConfidence: number | null;
  weatherStatus: "pending" | "fetched" | "failed" | "not_applicable" | null;
}

/**
 * Displays CdA/Crr estimation results with confidence indicator.
 * Shows appropriate messaging for each weather status state.
 */
export function AeroEstimateCard({
  estimatedCda,
  estimatedCrr,
  aeroConfidence,
  weatherStatus,
}: AeroEstimateCardProps) {
  // Don't show card if no data and not pending
  const hasData = estimatedCda !== null || estimatedCrr !== null;
  const isPending = weatherStatus === "pending" || weatherStatus === null;
  const isFailed = weatherStatus === "failed";
  const isNotApplicable = weatherStatus === "not_applicable";

  if (!hasData && !isPending && !isFailed && !isNotApplicable) {
    return null;
  }

  // Confidence color scale
  const getConfidenceColor = (conf: number | null) => {
    if (conf === null) return "text-muted-foreground";
    if (conf >= 0.7) return "text-success";
    if (conf >= 0.4) return "text-warning";
    return "text-destructive";
  };

  const getConfidenceLabel = (conf: number | null) => {
    if (conf === null) return "—";
    if (conf >= 0.7) return "High";
    if (conf >= 0.4) return "Medium";
    return "Low";
  };

  // Wind icon for aero card
  const windIcon = (
    <svg className="w-5 h-5 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
    </svg>
  );

  // Status messages for non-data states
  if (isPending) {
    return (
      <MetricGroupCard icon={windIcon} title="Aero Estimate">
        <div className="text-body-secondary text-sm">
          <p>Weather data pending</p>
          <p className="text-caption mt-1">CdA/Crr will be calculated after weather is fetched</p>
        </div>
      </MetricGroupCard>
    );
  }

  if (isFailed && !hasData) {
    return (
      <MetricGroupCard icon={windIcon} title="Aero Estimate">
        <div className="text-body-secondary text-sm">
          <p>Weather fetch failed</p>
          <p className="text-caption mt-1">Unable to estimate aerodynamics without weather data</p>
        </div>
      </MetricGroupCard>
    );
  }

  if (isNotApplicable && !hasData) {
    return (
      <MetricGroupCard icon={windIcon} title="Aero Estimate">
        <div className="text-body-secondary text-sm">
          <p>Not available</p>
          <p className="text-caption mt-1">Requires outdoor ride with GPS and power data</p>
        </div>
      </MetricGroupCard>
    );
  }

  // Show actual data
  return (
    <MetricGroupCard icon={windIcon} title="Aero Estimate">
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex justify-between items-baseline cursor-help">
            <span className="text-muted-foreground text-sm flex items-center gap-1">
              CdA
              <svg className="w-3 h-3 text-muted-foreground" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </span>
            <span className="font-semibold text-lg text-foreground tabular-nums">
              {estimatedCda !== null ? estimatedCda.toFixed(3) : "—"} m²
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <p className="font-medium">Drag Area (CdA)</p>
          <p className="text-xs mt-1">Coefficient of drag × frontal area. Typical values: Road 0.25-0.35, TT 0.20-0.25</p>
        </TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex justify-between items-baseline cursor-help">
            <span className="text-muted-foreground text-sm flex items-center gap-1">
              Crr
              <svg className="w-3 h-3 text-muted-foreground" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </span>
            <span className="font-semibold text-lg text-foreground tabular-nums">
              {estimatedCrr !== null ? estimatedCrr.toFixed(4) : "—"}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <p className="font-medium">Rolling Resistance (Crr)</p>
          <p className="text-xs mt-1">Tire/surface friction coefficient. Typical values: Smooth road 0.003-0.005, Gravel 0.006-0.010</p>
        </TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex justify-between items-baseline cursor-help">
            <span className="text-muted-foreground text-sm flex items-center gap-1">
              Confidence
              <svg className="w-3 h-3 text-muted-foreground" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </span>
            <span className={`font-semibold text-lg tabular-nums ${getConfidenceColor(aeroConfidence)}`}>
              {getConfidenceLabel(aeroConfidence)}
              {aeroConfidence !== null && ` (${Math.round(aeroConfidence * 100)}%)`}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <p className="font-medium">Estimation Confidence</p>
          <p className="text-xs mt-1">Based on grade variety, data points, and weather quality. Higher is better.</p>
        </TooltipContent>
      </Tooltip>
    </MetricGroupCard>
  );
}
