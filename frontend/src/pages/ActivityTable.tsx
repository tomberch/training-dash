import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import type { Activity, PaginationMeta } from "../api";
import { ApiError, fetchActivities } from "../api";
import { formatDistance, formatTime, formatDate, formatElevation, formatSpeed } from "../format";
import type { UnitSystem } from "../format";
import { ErrorDisplay } from "../ErrorDisplay";

type SortField = "date" | "distance" | "time" | "elevation" | "tss" | "power" | "hr";
type SortDirection = "asc" | "desc";

// Sort icon component
function SortIcon({ active, direction }: { active: boolean; direction: SortDirection }) {
  return (
    <span className={`ml-1 inline-block ${active ? "text-indigo-600 dark:text-indigo-400" : "text-gray-400"}`}>
      {active && direction === "asc" ? "↑" : active && direction === "desc" ? "↓" : "↕"}
    </span>
  );
}

// Table header cell with sorting
function SortableHeader({
  label,
  field,
  currentSort,
  currentDirection,
  onSort,
  className = "",
}: {
  label: string;
  field: SortField;
  currentSort: SortField;
  currentDirection: SortDirection;
  onSort: (field: SortField) => void;
  className?: string;
}) {
  return (
    <th
      className={`px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 select-none ${className}`}
      onClick={() => onSort(field)}
    >
      <span className="flex items-center">
        {label}
        <SortIcon active={currentSort === field} direction={currentDirection} />
      </span>
    </th>
  );
}

// Pagination component
function Pagination({
  pagination,
  onPageChange,
}: {
  pagination: PaginationMeta;
  onPageChange: (page: number) => void;
}) {
  const { page, total_pages } = pagination;

  const getPageNumbers = () => {
    const pages: (number | "...")[] = [];

    if (total_pages <= 7) {
      for (let i = 1; i <= total_pages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (page > 3) pages.push("...");
      for (let i = Math.max(2, page - 1); i <= Math.min(total_pages - 1, page + 1); i++) {
        pages.push(i);
      }
      if (page < total_pages - 2) pages.push("...");
      pages.push(total_pages);
    }

    return pages;
  };

  if (total_pages <= 1) return null;

  return (
    <div className="flex items-center justify-center gap-1 mt-4">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page === 1}
        className="px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Previous
      </button>

      <div className="flex items-center gap-1">
        {getPageNumbers().map((p, i) =>
          p === "..." ? (
            <span key={`ellipsis-${i}`} className="px-2 text-gray-500">
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`w-10 h-10 text-sm font-medium rounded-lg transition-colors ${
                p === page
                  ? "bg-indigo-600 text-white"
                  : "text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
              }`}
            >
              {p}
            </button>
          )
        )}
      </div>

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page === total_pages}
        className="px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Next
      </button>
    </div>
  );
}

export function ActivityTable({ unitSystem = "metric" }: { unitSystem?: UnitSystem }) {
  const navigate = useNavigate();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  useEffect(() => {
    setLoading(true);
    fetchActivities(currentPage, 50) // 50 per page for table view
      .then((result) => {
        setActivities(result.activities);
        setPagination(result.pagination);
      })
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, [currentPage]);

  // Client-side sorting (since API doesn't support sort yet)
  const sortedActivities = [...activities].sort((a, b) => {
    let cmp = 0;
    switch (sortField) {
      case "date":
        cmp = new Date(a.started_at).getTime() - new Date(b.started_at).getTime();
        break;
      case "distance":
        cmp = a.total_distance_m - b.total_distance_m;
        break;
      case "time":
        cmp = a.moving_time_s - b.moving_time_s;
        break;
      case "elevation":
        cmp = a.elevation_gain_m - b.elevation_gain_m;
        break;
      case "tss":
        cmp = (a.tss ?? 0) - (b.tss ?? 0);
        break;
      case "power":
        cmp = (a.avg_power_w ?? 0) - (b.avg_power_w ?? 0);
        break;
      case "hr":
        cmp = (a.avg_hr_bpm ?? 0) - (b.avg_hr_bpm ?? 0);
        break;
    }
    return sortDirection === "asc" ? cmp : -cmp;
  });

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <ErrorDisplay error={error} context="loading activities" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">Activity Table</h1>
          <button
            onClick={() => navigate("/activities")}
            className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
            title="View as list"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            List view
          </button>
        </div>
        {pagination && (
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {pagination.total} {pagination.total === 1 ? "activity" : "activities"}
          </span>
        )}
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <SortableHeader
                  label="Date"
                  field="date"
                  currentSort={sortField}
                  currentDirection={sortDirection}
                  onSort={handleSort}
                />
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Title
                </th>
                <SortableHeader
                  label="Distance"
                  field="distance"
                  currentSort={sortField}
                  currentDirection={sortDirection}
                  onSort={handleSort}
                  className="text-right"
                />
                <SortableHeader
                  label="Time"
                  field="time"
                  currentSort={sortField}
                  currentDirection={sortDirection}
                  onSort={handleSort}
                  className="text-right"
                />
                <SortableHeader
                  label="Elevation"
                  field="elevation"
                  currentSort={sortField}
                  currentDirection={sortDirection}
                  onSort={handleSort}
                  className="text-right"
                />
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Avg Speed
                </th>
                <SortableHeader
                  label="TSS"
                  field="tss"
                  currentSort={sortField}
                  currentDirection={sortDirection}
                  onSort={handleSort}
                  className="text-right"
                />
                <SortableHeader
                  label="Avg Power"
                  field="power"
                  currentSort={sortField}
                  currentDirection={sortDirection}
                  onSort={handleSort}
                  className="text-right"
                />
                <SortableHeader
                  label="Avg HR"
                  field="hr"
                  currentSort={sortField}
                  currentDirection={sortDirection}
                  onSort={handleSort}
                  className="text-right"
                />
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  NP
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  IF
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {loading
                ? [...Array(10)].map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="px-4 py-3">
                        <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded ml-auto"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-14 bg-gray-200 dark:bg-gray-700 rounded ml-auto"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-12 bg-gray-200 dark:bg-gray-700 rounded ml-auto"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded ml-auto"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-10 bg-gray-200 dark:bg-gray-700 rounded ml-auto"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-12 bg-gray-200 dark:bg-gray-700 rounded ml-auto"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-10 bg-gray-200 dark:bg-gray-700 rounded ml-auto"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-10 bg-gray-200 dark:bg-gray-700 rounded mx-auto"></div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 w-10 bg-gray-200 dark:bg-gray-700 rounded mx-auto"></div>
                      </td>
                    </tr>
                  ))
                : sortedActivities.map((activity) => (
                    <tr
                      key={activity.id}
                      onClick={() => navigate(`/activities/${activity.id}`)}
                      className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                    >
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                        {formatDate(activity.started_at)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 dark:text-white max-w-xs truncate">
                        <div className="flex items-center gap-2">
                          {activity.title || (
                            <span className="text-gray-400 italic">Untitled</span>
                          )}
                          {activity.is_breakthrough && (
                            <span
                              className="inline-flex items-center px-1.5 py-0.5 text-xs font-medium text-amber-800 bg-amber-100 dark:text-amber-200 dark:bg-amber-900/50 rounded"
                              title="Breakthrough activity"
                            >
                              ★
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white text-right tabular-nums">
                        {formatDistance(activity.total_distance_m, unitSystem)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white text-right tabular-nums">
                        {formatTime(activity.moving_time_s)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white text-right tabular-nums">
                        {formatElevation(activity.elevation_gain_m, unitSystem)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white text-right tabular-nums">
                        {formatSpeed(activity.avg_speed_mps, unitSystem)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white text-right tabular-nums">
                        {activity.tss != null ? Math.round(activity.tss) : "—"}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white text-right tabular-nums">
                        {activity.avg_power_w != null ? `${activity.avg_power_w} W` : "—"}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white text-right tabular-nums">
                        {activity.avg_hr_bpm != null ? activity.avg_hr_bpm : "—"}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 text-center tabular-nums">
                        {activity.np_power_w != null ? activity.np_power_w : "—"}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 text-center tabular-nums">
                        {activity.intensity_factor != null
                          ? activity.intensity_factor.toFixed(2)
                          : "—"}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>

        {/* Empty state */}
        {!loading && activities.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-gray-400">
              No activities yet. Upload a FIT file to get started.
            </p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {pagination && <Pagination pagination={pagination} onPageChange={handlePageChange} />}
    </div>
  );
}
