import { useState, useEffect } from "react";
import type { RecordsResponse } from "./api";
import { ApiError, fetchRecords } from "./api";
import { prsFromRecords, routePRsFromRecords } from "./prs";
import type { PR } from "./prs";
import type { UnitSystem } from "./format";
import { ErrorDisplay } from "./ErrorDisplay";

function PRTile({ pr, variant }: { pr: PR; variant: "lifetime" | "route" }) {
  const bgClass =
    variant === "lifetime"
      ? "bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800"
      : "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800";

  return (
    <div className={`p-4 rounded-lg border ${bgClass} text-center min-w-36`}>
      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
        {pr.label}
      </div>
      <div className="text-xl font-bold text-gray-900 dark:text-white tabular-nums">
        {pr.value}
      </div>
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
      <div className="text-gray-500 dark:text-gray-400">Loading...</div>
    );
  }

  const lifetimePRs = prsFromRecords(data.lifetime_prs, unitSystem);
  const routePRs = routePRsFromRecords(data.route_prs);

  if (lifetimePRs.length === 0 && routePRs.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Records</h1>
        <p className="text-gray-500 dark:text-gray-400">
          No activities yet. Upload a FIT file to see your PRs.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Records</h1>

      {lifetimePRs.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
            Lifetime PRs
          </h2>
          <PRGrid prs={lifetimePRs} variant="lifetime" />
        </section>
      )}

      {routePRs.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            Route PRs
          </h2>
          <PRGrid prs={routePRs} variant="route" />
        </section>
      )}
    </div>
  );
}
