/**
 * RideTypeBadge - Displays ride type with colored badge and tooltip showing resolved values
 */

import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";

export type RideType = "race" | "gran_fondo" | "training" | "touring" | "custom";

const RIDE_TYPE_LABELS: Record<RideType, string> = {
  race: "Race",
  gran_fondo: "Gran Fondo",
  training: "Training",
  touring: "Touring",
  custom: "Custom",
};

const RIDE_TYPE_COLORS: Record<RideType, string> = {
  race: "bg-destructive/20 text-destructive",
  gran_fondo: "bg-primary/20 text-primary",
  training: "bg-success/20 text-success",
  touring: "bg-muted text-muted-foreground",
  custom: "bg-warning/20 text-warning",
};

interface RideTypeBadgeProps {
  rideType: RideType | string | null;
  descentAggressiveness: number | null;
  stopPct: number | null;
  className?: string;
}

export function RideTypeBadge({
  rideType,
  descentAggressiveness,
  stopPct,
  className,
}: RideTypeBadgeProps) {
  if (!rideType) return null;

  const type = rideType as RideType;
  const label = RIDE_TYPE_LABELS[type] || rideType;
  const colorClass = RIDE_TYPE_COLORS[type] || RIDE_TYPE_COLORS.touring;

  const hasValues = descentAggressiveness !== null || stopPct !== null;

  const badge = (
    <span
      className={cn(
        "px-2.5 py-1 rounded-full text-xs font-medium",
        colorClass,
        className
      )}
    >
      {label}
    </span>
  );

  if (!hasValues) {
    return badge;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent>
        <div className="space-y-1">
          {descentAggressiveness !== null && (
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Descent</span>
              <span className="font-medium">{descentAggressiveness}/100</span>
            </div>
          )}
          {stopPct !== null && (
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Stops</span>
              <span className="font-medium">+{stopPct}%</span>
            </div>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
