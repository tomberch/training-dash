import { Skeleton } from "@/components/ui/skeleton";

export function ActivityDetailSkeleton(): React.JSX.Element {
  return (
    <div className="p-6">
      <div className="space-y-6">
        {/* Back link */}
        <Skeleton className="h-5 w-32" />
        
        {/* Title row with badge and edit icon */}
        <div className="flex items-start gap-2">
          <Skeleton className="h-8 w-96" />
          <Skeleton className="h-5 w-5 mt-1.5 rounded" />
        </div>
        
        {/* Subtitle row with date and action buttons */}
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-64" />
          <div className="flex gap-2">
            <Skeleton className="h-9 w-24 rounded-lg" />
            <Skeleton className="h-9 w-20 rounded-lg" />
          </div>
        </div>
        
        {/* Map */}
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="h-64 bg-muted flex items-center justify-center">
            <svg className="w-12 h-12 text-muted-foreground/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          {/* Resize handle placeholder */}
          <div className="h-3 bg-muted/80 flex items-center justify-center">
            <Skeleton className="w-20 h-1 rounded-full" />
          </div>
        </div>
        
        {/* Grouped metric cards skeleton */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-card rounded-xl border border-border p-5">
              <div className="flex items-center gap-2 mb-4">
                <Skeleton className="w-5 h-5 rounded" />
                <Skeleton className="h-3 w-24" />
              </div>
              <div className="space-y-3">
                {[1, 2].map((j) => (
                  <div key={j} className="flex justify-between items-baseline">
                    <Skeleton className="h-3 w-16" />
                    <Skeleton className="h-5 w-20" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        
        {/* Performance section */}
        <div>
          <Skeleton className="h-6 w-32 mb-2" />
          <Skeleton className="h-4 w-64 mb-4" />
        </div>
        
        {/* Chart */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="flex items-center justify-between mb-3">
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-8 w-16 rounded" />
          </div>
          <div className="h-48 bg-muted rounded flex items-end justify-around p-4 gap-1">
            {[40, 55, 35, 60, 45, 70, 50, 65, 45, 75, 55, 80, 60, 50, 70].map((h, i) => (
              <Skeleton key={i} className="flex-1 rounded-t" style={{ height: `${h}%` }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
