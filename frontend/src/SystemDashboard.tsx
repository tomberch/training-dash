import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  fetchSystemEvents,
  fetchActiveJobs,
  fetchCacheStats,
  abortJob,
  retryJob,
  type SystemEvent,
  type ActiveJob,
  type CacheStatsResponse,
  type SystemEventsFilters,
} from "./api";

// =============================================================================
// EVENT TYPE OPTIONS (grouped by domain)
// =============================================================================

const EVENT_TYPE_OPTIONS = [
  { group: "Activity", options: ["activity.ingested", "activity.deleted"] },
  { group: "Sync", options: ["sync.started", "sync.completed", "sync.lost_tick"] },
  { group: "Route", options: ["route.matched"] },
  { group: "Threshold", options: ["threshold.updated"] },
  { group: "Recalculation", options: ["recalculation.started", "recalculation.completed"] },
  {
    group: "Credentials",
    options: ["credentials.saved", "credentials.removed", "credentials.validation_failed"],
  },
  { group: "Breakthrough", options: ["breakthrough.detected"] },
  {
    group: "Job",
    options: ["job.completed", "job.failed", "job.enqueue_failed", "job.stuck"],
  },
  {
    group: "Admin",
    options: ["admin.nuke_activities", "admin.nuke_integrations", "admin.nuke_account"],
  },
  { group: "Scheduler", options: ["scheduler.triggered"] },
  { group: "Cache", options: ["cache.pruned"] },
];

// =============================================================================
// TYPES
// =============================================================================

type TimeRange = "1h" | "24h" | "7d" | "30d" | "90d";

interface Filters {
  eventType: string;
  outcome: string;
  userId: string;
  timeRange: TimeRange;
}

// =============================================================================
// HELPERS
// =============================================================================

function getTimeRangeSince(range: TimeRange): string {
  const now = new Date();
  const msPerHour = 60 * 60 * 1000;
  const msPerDay = 24 * msPerHour;
  
  const offsets: Record<TimeRange, number> = {
    "1h": msPerHour,
    "24h": msPerDay,
    "7d": 7 * msPerDay,
    "30d": 30 * msPerDay,
    "90d": 90 * msPerDay,
  };
  
  return new Date(now.getTime() - offsets[range]).toISOString();
}

function computeHitRate(hits: number, misses: number): number {
  const total = hits + misses;
  return total > 0 ? Math.round((hits / total) * 100) : 0;
}

function buildEventFilters(filters: Filters, offset: number, limit: number): SystemEventsFilters {
  const apiFilters: SystemEventsFilters = {
    limit,
    offset,
    since: getTimeRangeSince(filters.timeRange),
  };
  if (filters.eventType) apiFilters.event_type = filters.eventType;
  if (filters.outcome) apiFilters.outcome = filters.outcome;
  if (filters.userId) apiFilters.user_id = parseInt(filters.userId, 10);
  return apiFilters;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function SystemDashboard({ onBack }: { onBack: () => void }) {
  // Data state
  const [cacheStats, setCacheStats] = useState<CacheStatsResponse | null>(null);
  const [activeJobs, setActiveJobs] = useState<ActiveJob[]>([]);
  const [workersAlive, setWorkersAlive] = useState(0);
  const [jobStatusFilter, setJobStatusFilter] = useState<string>("all");
  const [busyJobKey, setBusyJobKey] = useState<string | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [totalEvents, setTotalEvents] = useState(0);

  // Loading state
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // Filter state
  const [filters, setFilters] = useState<Filters>({
    eventType: "",
    outcome: "",
    userId: "",
    timeRange: "24h",
  });

  // Pagination
  const [offset, setOffset] = useState(0);
  const limit = 50;

  // Initial load
  useEffect(() => {
    loadStats();
    loadJobs();
  }, []);

  // Reload events when filters change
  useEffect(() => {
    setOffset(0);
    setLoadingEvents(true);

    fetchSystemEvents(buildEventFilters(filters, 0, limit))
      .then(({ events: newEvents, total }) => {
        setEvents(newEvents);
        setTotalEvents(total);
      })
      .catch((e) => console.error("Failed to load events:", e))
      .finally(() => setLoadingEvents(false));
  }, [filters]);

  async function loadStats() {
    setLoadingStats(true);
    try {
      const stats = await fetchCacheStats(7);
      setCacheStats(stats);
    } catch (e) {
      console.error("Failed to load cache stats:", e);
    } finally {
      setLoadingStats(false);
    }
  }

  async function loadJobs() {
    setLoadingJobs(true);
    try {
      const { jobs, workers_alive } = await fetchActiveJobs();
      setActiveJobs(jobs);
      setWorkersAlive(workers_alive ?? 0);
    } catch (e) {
      console.error("Failed to load jobs:", e);
    } finally {
      setLoadingJobs(false);
    }
  }

  const filteredJobs =
    jobStatusFilter === "all" ? activeJobs : activeJobs.filter((j) => j.status === jobStatusFilter);

  const jobStatusBadge = (status: string) =>
    cn(
      "px-2 py-0.5 text-xs font-medium rounded-full",
      status === "active" && "bg-warning/20 text-warning",
      (status === "failed" || status === "aborted") && "bg-destructive/20 text-destructive",
      status === "queued" && "bg-muted text-muted-foreground",
      status === "processing" && "bg-muted text-muted-foreground",
      status === "complete" && "bg-success/20 text-success",
      !["active", "failed", "aborted", "queued", "processing", "complete"].includes(status) &&
        "bg-muted text-muted-foreground"
    );

  async function handleJobAction(job: ActiveJob, action: "abort" | "retry") {
    // ADR 0007: one confirmation — aborting an ACTIVE job may cancel mid-run work.
    if (action === "abort" && (job.status === "active" || job.status === "processing")) {
      const confirmed = window.confirm(
        "This will cancel a running job; data may be partially written. The job will be marked aborted and retried per policy. Continue?"
      );
      if (!confirmed) return;
    }
    setBusyJobKey(job.key);
    try {
      if (action === "abort") {
        await abortJob(job.key);
      } else {
        await retryJob(job.key);
      }
      await loadJobs();
    } catch (e) {
      console.error(`Failed to ${action} job:`, e);
      window.alert(`Failed to ${action} job: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusyJobKey(null);
    }
  }

  async function loadEvents(reset = false) {
    if (reset) {
      setLoadingEvents(true);
    } else {
      setLoadingMore(true);
    }

    try {
      const currentOffset = reset ? 0 : offset;
      const { events: newEvents, total } = await fetchSystemEvents(
        buildEventFilters(filters, currentOffset, limit)
      );

      if (reset) {
        setEvents(newEvents);
        setOffset(0);
      } else {
        setEvents((prev) => [...prev, ...newEvents]);
      }
      setTotalEvents(total);
    } catch (e) {
      console.error("Failed to load events:", e);
    } finally {
      setLoadingEvents(false);
      setLoadingMore(false);
    }
  }

  function handleRefresh() {
    loadStats();
    loadJobs();
    setOffset(0);
    loadEvents(true);
  }

  function handleLoadMore() {
    const newOffset = offset + limit;
    setOffset(newOffset);
    loadEvents(false);
  }

  function handleClearFilters() {
    setFilters({ eventType: "", outcome: "", userId: "", timeRange: "24h" });
  }

  // Calculate hit rates
  const tileHits = cacheStats?.current.tiles?.hits ?? 0;
  const tileMisses = cacheStats?.current.tiles?.misses ?? 0;
  const tileHitRate = computeHitRate(tileHits, tileMisses);

  const geoHits = cacheStats?.current.geocoding?.hits ?? 0;
  const geoMisses = cacheStats?.current.geocoding?.misses ?? 0;
  const geoHitRate = computeHitRate(geoHits, geoMisses);

  const hasMore = events.length < totalEvents;

  return (
    <div className="px-4 py-6">
      {/* ===== HEADER ===== */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" onClick={onBack}>
            &larr; Back
          </Button>
          <h1 className="text-page-title">System Dashboard</h1>
        </div>
        <Button variant="outline" onClick={handleRefresh}>
          Refresh
        </Button>
      </div>

      {/* ===== STATS BAR ===== */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {/* Active Jobs */}
        <Card>
          <CardContent className="pt-4">
            {loadingJobs ? (
              <StatsCardSkeleton />
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-label">Jobs</p>
                    <p className="text-metric">{activeJobs.length}</p>
                  </div>
                  <div
                    className={cn(
                      "w-3 h-3 rounded-full",
                      activeJobs.some((j) => j.status === "failed" || j.status === "aborted")
                        ? "bg-destructive"
                        : activeJobs.length > 0
                          ? "bg-warning animate-pulse"
                          : "bg-success"
                    )}
                  />
                </div>
                <p className="text-caption mt-2">
                  {workersAlive > 0
                    ? `${workersAlive} worker${workersAlive === 1 ? "" : "s"} alive`
                    : "no live workers"}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Tile Cache */}
        <Card>
          <CardContent className="pt-4">
            {loadingStats ? (
              <StatsCardSkeleton />
            ) : (
              <>
                <p className="text-label">Tile Cache</p>
                <p className="text-metric">
                  {tileHitRate}%
                  <span className="text-body-secondary ml-2">hit rate</span>
                </p>
                <p className="text-caption mt-1">
                  {cacheStats?.sizes.tiles_mb.toFixed(1)} MB ({tileHits + tileMisses} requests)
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Geocoding Cache */}
        <Card>
          <CardContent className="pt-4">
            {loadingStats ? (
              <StatsCardSkeleton />
            ) : (
              <>
                <p className="text-label">Geocoding Cache</p>
                <p className="text-metric">
                  {geoHitRate}%
                  <span className="text-body-secondary ml-2">hit rate</span>
                </p>
                <p className="text-caption mt-1">
                  {cacheStats?.sizes.geocoding_count.toLocaleString()} entries
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ===== JOBS SECTION ===== */}
      {!loadingJobs && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <CardTitle>Jobs ({filteredJobs.length})</CardTitle>
              {/* Status filter (ADR 0007): failed/stuck rows are the recent SAQ tail */}
              <select
                className="px-3 py-2 text-sm border border-input rounded-lg bg-background text-foreground"
                value={jobStatusFilter}
                onChange={(e) => setJobStatusFilter(e.target.value)}
              >
                <option value="all">All statuses</option>
                <option value="active">Active</option>
                <option value="queued">Queued</option>
                <option value="failed">Failed</option>
                <option value="aborted">Aborted</option>
              </select>
            </div>
          </CardHeader>
          <CardContent>
            {filteredJobs.length === 0 ? (
              <p className="text-caption py-4">No jobs with this status in SAQ retention (~10 min tail).</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="py-2 px-3 text-left text-section-heading">Job</th>
                      <th className="py-2 px-3 text-left text-section-heading">Status</th>
                      <th className="py-2 px-3 text-left text-section-heading">Attempts</th>
                      <th className="py-2 px-3 text-left text-section-heading">Started</th>
                      <th className="py-2 px-3 text-left text-section-heading">Key</th>
                      <th className="py-2 px-3 text-left text-section-heading">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredJobs.map((job) => (
                      <tr key={job.key} className="border-b border-border last:border-0">
                        <td className="py-2 px-3 text-sm font-medium text-foreground">
                          {job.function.replace(/_/g, " ")}
                        </td>
                        <td className="py-2 px-3">
                          <span className={jobStatusBadge(job.status)}>{job.status}</span>
                        </td>
                        <td className="py-2 px-3 text-caption">{job.attempts}</td>
                        <td className="py-2 px-3 text-caption">
                          {job.started ? new Date(job.started).toLocaleTimeString() : "—"}
                        </td>
                        <td className="py-2 px-3 text-caption font-mono">{job.key.slice(0, 8)}...</td>
                        <td className="py-2 px-3">
                          <div className="flex gap-2">
                            {(job.status === "failed" || job.status === "aborted") && (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={busyJobKey === job.key}
                                onClick={() => handleJobAction(job, "retry")}
                              >
                                Retry
                              </Button>
                            )}
                            {(job.status === "active" ||
                              job.status === "processing" ||
                              job.status === "queued") && (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={busyJobKey === job.key}
                                onClick={() => handleJobAction(job, "abort")}
                              >
                                Abort
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ===== EVENT STREAM ===== */}
      <Card>
        <CardHeader>
          <CardTitle>Event Stream</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-wrap gap-3 mb-4 pb-4 border-b border-border">
            {/* Event Type Filter */}
            <select
              className="px-3 py-2 text-sm border border-input rounded-lg bg-background text-foreground"
              value={filters.eventType}
              onChange={(e) => setFilters({ ...filters, eventType: e.target.value })}
            >
              <option value="">All event types</option>
              {EVENT_TYPE_OPTIONS.map((group) => (
                <optgroup key={group.group} label={group.group}>
                  {group.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>

            {/* Outcome Filter */}
            <select
              className="px-3 py-2 text-sm border border-input rounded-lg bg-background text-foreground"
              value={filters.outcome}
              onChange={(e) => setFilters({ ...filters, outcome: e.target.value })}
            >
              <option value="">All outcomes</option>
              <option value="success">Success</option>
              <option value="failure">Failure</option>
              <option value="info">Info</option>
            </select>

            {/* User Filter */}
            <Input
              type="text"
              placeholder="User ID"
              className="w-24"
              value={filters.userId}
              onChange={(e) => setFilters({ ...filters, userId: e.target.value })}
            />

            {/* Time Range Filter */}
            <select
              className="px-3 py-2 text-sm border border-input rounded-lg bg-background text-foreground"
              value={filters.timeRange}
              onChange={(e) => setFilters({ ...filters, timeRange: e.target.value as TimeRange })}
            >
              <option value="1h">Last hour</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
            </select>

            {/* Clear Filters */}
            <Button variant="ghost" size="sm" onClick={handleClearFilters}>
              Clear filters
            </Button>
          </div>

          {/* Event List */}
          {loadingEvents ? (
            <EventListSkeleton />
          ) : events.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No events found for the selected filters.
            </div>
          ) : (
            <div className="space-y-2">
              {events.map((event) => (
                <EventRow key={event.id} event={event} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {!loadingEvents && hasMore && (
            <div className="flex justify-center mt-4 pt-4 border-t border-border">
              <Button variant="outline" size="sm" onClick={handleLoadMore} disabled={loadingMore}>
                {loadingMore ? "Loading..." : "Load more"}
              </Button>
            </div>
          )}

          {/* Total count */}
          {!loadingEvents && events.length > 0 && (
            <p className="text-center text-caption mt-2">
              Showing {events.length} of {totalEvents} events
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// =============================================================================
// EVENT ROW COMPONENT
// =============================================================================

function EventRow({ event }: { event: SystemEvent }) {
  const [expanded, setExpanded] = useState(false);

  const outcomeColors = {
    success: "bg-success/20 text-success",
    failure: "bg-destructive/20 text-destructive",
    info: "bg-muted text-muted-foreground",
  };

  const [domain, action] = event.event_type.split(".");

  // Format relative time
  const eventTime = new Date(event.created_at);
  const now = new Date();
  const diffMs = now.getTime() - eventTime.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  let relativeTime: string;
  if (diffMins < 1) {
    relativeTime = "just now";
  } else if (diffMins < 60) {
    relativeTime = `${diffMins}m ago`;
  } else if (diffHours < 24) {
    relativeTime = `${diffHours}h ago`;
  } else {
    relativeTime = `${diffDays}d ago`;
  }

  return (
    <div
      className="p-3 rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Outcome badge */}
          <span className={cn("px-2 py-0.5 text-xs font-medium rounded-full", outcomeColors[event.outcome])}>
            {event.outcome}
          </span>

          {/* Event type */}
          <span className="text-sm font-medium text-foreground">
            {domain}.<span className="text-muted-foreground">{action}</span>
          </span>

          {/* User */}
          {event.user_email && <span className="text-caption">{event.user_email}</span>}
          {event.user_id && !event.user_email && <span className="text-caption">user {event.user_id}</span>}
        </div>

        {/* Timestamp */}
        <span className="text-caption" title={eventTime.toLocaleString()}>
          {relativeTime}
        </span>
      </div>

      {/* Expanded payload */}
      {expanded && Object.keys(event.payload).length > 0 && (
        <div className="mt-3 pt-3 border-t border-border">
          <pre className="text-xs text-muted-foreground bg-muted p-2 rounded overflow-x-auto">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// SKELETON COMPONENTS
// =============================================================================

function StatsCardSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

function EventListSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="p-3 rounded-lg border border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-16" />
            </div>
            <Skeleton className="h-3 w-12" />
          </div>
        </div>
      ))}
    </div>
  );
}
