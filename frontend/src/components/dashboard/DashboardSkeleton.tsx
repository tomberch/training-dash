/**
 * Dashboard loading skeleton component
 */
import type { JSX } from "react";
import { Skeleton } from "@/components/ui/skeleton";

export function DashboardSkeleton(): JSX.Element {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <Skeleton className="h-9 w-40" />
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-28 rounded-lg" />
          <Skeleton className="h-10 w-10 rounded-full" />
        </div>
      </div>
      
      {/* Top Row: PMC + Weekly Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* PMC Sparkline skeleton */}
        <div className="lg:col-span-2 bg-card rounded-xl border border-border p-6">
          <div className="flex items-center justify-between mb-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-6 w-20 rounded-full" />
          </div>
          <div className="h-40 bg-muted rounded flex items-end justify-around p-4 gap-1">
            {[40, 55, 35, 60, 45, 70, 50, 65, 45, 75, 55, 80].map((h, i) => (
              <Skeleton key={i} className="w-3 rounded-t" style={{ height: `${h}%` }} />
            ))}
          </div>
          <div className="flex gap-6 mt-2">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
        
        {/* Weekly Summary skeleton */}
        <div className="bg-card rounded-xl border border-border p-6">
          <Skeleton className="h-4 w-20 mb-3" />
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex justify-between">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-12" />
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Recent Activities */}
      <div className="bg-card rounded-xl border border-border p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <Skeleton className="h-6 w-36" />
          <Skeleton className="h-4 w-16" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-muted/30 rounded-xl border border-border overflow-hidden">
              <Skeleton className="h-40 rounded-none" />
              <div className="p-4 space-y-3">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-3 w-32" />
                <div className="grid grid-cols-3 gap-2">
                  {[1, 2, 3].map((j) => (
                    <div key={j} className="text-center">
                      <Skeleton className="h-3 w-12 mx-auto" />
                    </div>
                  ))}
                </div>
                <div className="pt-3 border-t border-border">
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Power Curve thumbnail skeleton */}
      <div className="bg-card rounded-xl border border-border p-6">
        <Skeleton className="h-4 w-24 mb-2" />
        <div className="h-24 bg-muted rounded flex items-end justify-around p-2 gap-0.5">
          {[95, 85, 75, 68, 62, 58, 55, 52, 50, 48, 46, 44, 42, 40, 38].map((h, i) => (
            <Skeleton key={i} className="flex-1 rounded-t" style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    </div>
  );
}
