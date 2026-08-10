import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import type { RecordsResponse } from "./api";
import { ApiError, fetchRecords } from "./api";
import { prsFromRecords, routePRsFromRecords } from "./prs";
import type { PR } from "./prs";
import type { UnitSystem } from "./format";
import { ErrorDisplay } from "./ErrorDisplay";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

function PRTile({ pr, variant }: { pr: PR; variant: "lifetime" | "route" }) {
  const bgClass =
    variant === "lifetime"
      ? "bg-primary/10 border-primary/30"
      : "bg-success/10 border-success/30";

  const content = (
    <>
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
        {pr.label}
      </div>
      <div className="text-3xl font-bold text-foreground tabular-nums mb-2">
        {pr.value}
      </div>
      {pr.activityId ? (
        <div className="group flex items-center justify-center gap-1.5 text-primary hover:text-primary-hover text-xs font-medium transition mt-auto pt-3 border-t border-current border-opacity-20 cursor-pointer">
          <span>View activity</span>
          <svg className="w-3.5 h-3.5 transform group-hover:translate-x-0.5 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </div>
      ) : (
        <div className="h-4 mt-auto" />
      )}
    </>
  );

  if (pr.activityId) {
    return (
      <Link
        to={`/activities/${pr.activityId}`}
        className={`p-5 rounded-lg border ${bgClass} text-center min-w-40 flex flex-col hover:shadow-lg transition-shadow`}
      >
        {content}
      </Link>
    );
  }

  return (
    <div className={`p-5 rounded-lg border ${bgClass} text-center min-w-40 flex flex-col`}>
      {content}
    </div>
  );
}

function PRGrid({ prs, variant }: { prs: PR[]; variant: "lifetime" | "route" }) {
  return (
    <div className="flex flex-wrap gap-3">
      {prs.map((pr) => (
        <PRTile key={pr.label} pr={pr} variant={variant} />
      ))}
    </div>
  );
}

interface RecordsViewProps {
  unitSystem?: UnitSystem;
}

export function RecordsView({ unitSystem = "metric" }: RecordsViewProps) {
  const [data, setData] = useState<RecordsResponse | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);

  useEffect(() => {
    fetchRecords()
      .then(setData)
      .catch((e) => setError(e));
  }, []);

  if (error) {
    return <ErrorDisplay error={error} context="loading records" />;
  }

  if (!data) {
    return (
      <div className="space-y-8">
        {/* Lifetime PRs skeleton */}
        <div>
          <Skeleton className="h-6 w-32 mb-4" />
          <div className="flex flex-wrap gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="p-5 rounded-lg border border-border bg-card text-center min-w-40 flex flex-col">
                <Skeleton className="h-3 w-20 mx-auto mb-2" />
                <Skeleton className="h-9 w-16 mx-auto mb-2" />
                <Skeleton className="h-3 w-24 mx-auto mt-auto" />
              </div>
            ))}
          </div>
        </div>
        
        {/* Route PRs skeleton */}
        <div>
          <Skeleton className="h-6 w-28 mb-4" />
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-card rounded-lg border border-border p-4">
                <Skeleton className="h-5 w-48 mb-3" />
                <div className="flex flex-wrap gap-3">
                  {[1, 2, 3, 4].map((j) => (
                    <div key={j} className="p-4 rounded border border-border text-center min-w-32 flex flex-col">
                      <Skeleton className="h-3 w-16 mx-auto mb-1" />
                      <Skeleton className="h-6 w-12 mx-auto mb-2" />
                      <Skeleton className="h-3 w-20 mx-auto mt-auto" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const lifetimePRs = prsFromRecords(data.lifetime_prs, unitSystem);
  const routePRs = routePRsFromRecords(data.route_prs);

  if (lifetimePRs.length === 0 && routePRs.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-foreground mb-4">Records</h1>
        <div className="bg-card rounded-lg border border-border">
          <EmptyState
            icon={
              <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
              </svg>
            }
            title="No personal records yet"
            description="Complete some activities to start tracking your PRs for power, distance, climbing, and more."
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-foreground">Records</h1>

      {lifetimePRs.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary"></span>
            Lifetime PRs
          </h2>
          <PRGrid prs={lifetimePRs} variant="lifetime" />
        </section>
      )}

      {routePRs.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-success"></span>
            Route PRs
          </h2>
          <PRGrid prs={routePRs} variant="route" />
        </section>
      )}
    </div>
  );
}
