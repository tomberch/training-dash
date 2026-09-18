/**
 * Shared segment UI primitives: category badge, type icon.
 *
 * Used by the segments browser, segment detail, and suggestion surfaces.
 */

import type { JSX } from "react";
import { cn } from "@/lib/utils";
import type { ClimbCategory, SegmentType } from "@/api/segments";

/** Climb category display configuration */
export const CLIMB_CATEGORY_CONFIG: Record<ClimbCategory, { label: string; color: string }> = {
  hc: { label: "HC", color: "bg-purple-600 text-white" },
  "1": { label: "Cat 1", color: "bg-red-600 text-white" },
  "2": { label: "Cat 2", color: "bg-orange-500 text-white" },
  "3": { label: "Cat 3", color: "bg-yellow-500 text-black" },
  "4": { label: "Cat 4", color: "bg-green-500 text-white" },
  nc: { label: "NC", color: "bg-muted text-muted-foreground" },
};

export function ClimbCategoryBadge({ category }: { category: ClimbCategory | null }): JSX.Element | null {
  if (!category) return null;
  const config = CLIMB_CATEGORY_CONFIG[category];
  return (
    <span className={cn("px-2 py-0.5 rounded text-xs font-bold", config.color)}>
      {config.label}
    </span>
  );
}

const TYPE_ICONS: Record<SegmentType, { icon: string; color: string }> = {
  climb: { icon: "▲", color: "text-orange-500" },
  sprint: { icon: "⚡", color: "text-blue-500" },
  custom: { icon: "◆", color: "text-muted-foreground" },
};

export function SegmentTypeIcon({ type }: { type: SegmentType }): JSX.Element {
  const { icon, color } = TYPE_ICONS[type];
  return (
    <span className={cn("text-lg", color)} aria-hidden>
      {icon}
    </span>
  );
}
