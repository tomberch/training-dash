/**
 * SustainabilityBadge - Displays plan sustainability level (green/yellow/red)
 *
 * ADR 0005: Every plan carries a sustainability level:
 * - green: sustainable for the ride duration
 * - yellow: very hard, near the rider's limit
 * - red: beyond capability (still saved, flagged)
 */

import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";

export type SustainabilityLevel = "green" | "yellow" | "red";

const SUSTAINABILITY_CONFIG: Record<
  SustainabilityLevel,
  { label: string; colorClass: string; description: string }
> = {
  green: {
    label: "Sustainable",
    colorClass: "bg-success/20 text-success",
    description: "This effort is sustainable for the planned duration.",
  },
  yellow: {
    label: "Very Hard",
    colorClass: "bg-warning/20 text-warning",
    description: "Near your limit — achievable but demanding. Pacing errors will hurt.",
  },
  red: {
    label: "Beyond Limit",
    colorClass: "bg-destructive/20 text-destructive",
    description: "Beyond your sustainable capability. Use as a strategy reference, not a ride plan.",
  },
};

interface SustainabilityBadgeProps {
  sustainability: SustainabilityLevel | string | null;
  className?: string;
  /** Show compact version (icon only) */
  compact?: boolean;
}

export function SustainabilityBadge({
  sustainability,
  className,
  compact = false,
}: SustainabilityBadgeProps) {
  if (!sustainability) return null;

  const level = sustainability as SustainabilityLevel;
  const config = SUSTAINABILITY_CONFIG[level];

  if (!config) return null;

  const badge = (
    <span
      className={cn(
        "px-2.5 py-1 rounded-full text-xs font-medium inline-flex items-center gap-1.5",
        config.colorClass,
        className
      )}
    >
      {/* Traffic light dot */}
      <span
        className={cn(
          "w-2 h-2 rounded-full",
          level === "green" && "bg-success",
          level === "yellow" && "bg-warning",
          level === "red" && "bg-destructive"
        )}
      />
      {!compact && config.label}
    </span>
  );

  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p>{config.description}</p>
      </TooltipContent>
    </Tooltip>
  );
}
