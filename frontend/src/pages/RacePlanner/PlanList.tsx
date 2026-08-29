/**
 * Plan List Page
 *
 * Table of user's race plans with:
 * - Sortable columns
 * - Actions: View, Compare, Delete
 */

import { useState, useEffect, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { SustainabilityBadge } from "@/components/race-planner";
import { fetchRacePlans, deleteRacePlan } from "@/api/race-plans";
import type { RacePlanListItem } from "@/api/types";
import { formatDateFull } from "./utils";

// =============================================================================
// Sort Types
// =============================================================================

type SortField = "name" | "time" | "power" | "created";
type SortDirection = "asc" | "desc";

// =============================================================================
// Sort Indicator Component
// =============================================================================

function SortIndicator({
  field,
  sortField,
  sortDirection,
}: {
  field: SortField;
  sortField: SortField;
  sortDirection: SortDirection;
}) {
  if (sortField !== field) return null;
  return <span className="ml-1">{sortDirection === "asc" ? "↑" : "↓"}</span>;
}

// =============================================================================
// Main Component
// =============================================================================

export function PlanList() {
  const navigate = useNavigate();
  const [plans, setPlans] = useState<RacePlanListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("created");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    setIsLoading(true);
    fetchRacePlans()
      .then(setPlans)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, []);

  const sortedPlans = useMemo(() => {
    const sorted = [...plans];
    sorted.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "name":
          cmp = (a.name || "").localeCompare(b.name || "");
          break;
        case "time":
          cmp = a.total_time_s - b.total_time_s;
          break;
        case "power":
          cmp = a.avg_power_w - b.avg_power_w;
          break;
        case "created":
          cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
      }
      return sortDirection === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [plans, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const handleDelete = async (planId: number) => {
    setDeletingId(planId);
    try {
      await deleteRacePlan(planId);
      setPlans((prev) => prev.filter((p) => p.id !== planId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  };


  if (isLoading) {
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-32 mb-2" />
        <Skeleton className="h-4 w-48 mb-8" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg mb-4">
          Failed to load plans: {error}
        </div>
        <Button variant="outline" onClick={() => navigate("/race-planner")}>
          Back to Race Planner
        </Button>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
            <Link to="/race-planner" className="hover:text-foreground">
              Race Planner
            </Link>
            <span>/</span>
            <span>Plans</span>
          </div>
          <h1 className="text-page-title">Plans</h1>
          <p className="text-page-subtitle mt-1">
            {plans.length} plan{plans.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Button onClick={() => navigate("/race-planner/generate")}>
          Generate Plan
        </Button>
      </div>

      {plans.length === 0 ? (
        <div className="bg-card border border-border rounded-xl p-8 text-center">
          <p className="text-muted-foreground mb-4">No plans yet</p>
          <Button onClick={() => navigate("/race-planner/generate")}>
            Generate Your First Plan
          </Button>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th
                    className="text-left py-3 px-4 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                    onClick={() => handleSort("name")}
                  >
                    Name <SortIndicator field="name" sortField={sortField} sortDirection={sortDirection} />
                  </th>
                  <th
                    className="text-right py-3 px-4 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                    onClick={() => handleSort("time")}
                  >
                    Time <SortIndicator field="time" sortField={sortField} sortDirection={sortDirection} />
                  </th>
                  <th
                    className="text-right py-3 px-4 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                    onClick={() => handleSort("power")}
                  >
                    Avg Power <SortIndicator field="power" sortField={sortField} sortDirection={sortDirection} />
                  </th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">
                    Method
                  </th>
                  <th
                    className="text-left py-3 px-4 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                    onClick={() => handleSort("created")}
                  >
                    Created <SortIndicator field="created" sortField={sortField} sortDirection={sortDirection} />
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedPlans.map((plan) => (
                  <tr
                    key={plan.id}
                    className="border-b border-border/50 hover:bg-muted/20 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <Link
                          to={`/race-planner/plans/${plan.id}`}
                          className="font-medium hover:text-primary hover:underline"
                        >
                          {plan.name || "Untitled Plan"}
                        </Link>
                        <SustainabilityBadge sustainability={plan.sustainability} compact />
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right tabular-nums">
                      {plan.total_time_formatted}
                    </td>
                    <td className="py-3 px-4 text-right tabular-nums">
                      {Math.round(plan.avg_power_w)} W
                    </td>
                    <td className="py-3 px-4 text-xs text-muted-foreground capitalize">
                      {plan.optimization_method || "heuristic"}
                    </td>
                    <td className="py-3 px-4 text-muted-foreground">
                      {formatDateFull(plan.created_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/race-planner/plans/${plan.id}/compare`)}
                        >
                          Compare
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              disabled={deletingId === plan.id}
                            >
                              Delete
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Plan</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to delete "{plan.name || "this plan"}"?
                                This cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(plan.id)}>
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
