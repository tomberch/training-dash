import { cn } from "@/lib/utils";
import type { BikeType } from "@/api/types";
import { BIKE_TYPE_LABELS } from "@/api/types";

const BIKE_TYPE_COLORS: Record<BikeType, string> = {
  road: "bg-blue-500/20 text-blue-600",
  gravel: "bg-amber-500/20 text-amber-600",
  mtb: "bg-emerald-500/20 text-emerald-600",
  tt: "bg-purple-500/20 text-purple-600",
  track: "bg-pink-500/20 text-pink-600",
  cx: "bg-orange-500/20 text-orange-600",
  commuter: "bg-slate-500/20 text-slate-600",
  ebike: "bg-cyan-500/20 text-cyan-600",
  other: "bg-muted text-muted-foreground",
};

interface BikeTypeBadgeProps {
  type: BikeType;
  className?: string;
}

export function BikeTypeBadge({ type, className }: BikeTypeBadgeProps) {
  return (
    <span
      className={cn(
        "px-2 py-0.5 rounded-full text-xs font-medium",
        BIKE_TYPE_COLORS[type] || BIKE_TYPE_COLORS.other,
        className
      )}
    >
      {BIKE_TYPE_LABELS[type] || type}
    </span>
  );
}
