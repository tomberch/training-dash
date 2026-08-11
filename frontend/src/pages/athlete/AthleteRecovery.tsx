import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  MetricTimelineChart,
  type MetricEntry,
  type TimeRange,
} from "@/components/MetricTimelineChart";
import {
  MetricEntryModal,
  type MetricType,
  type MetricEntryCreate,
  type MetricEntryUpdate,
} from "@/components/MetricEntryModal";
import {
  fetchMetrics,
  createMetric,
  updateMetric,
  deleteMetric,
  type MetricEntryResponse,
} from "@/api";

// Metric type definitions
const METRIC_TYPES: Record<string, MetricType> = {
  resting_hr: {
    key: "resting_hr",
    display_name: "Resting HR",
    unit: "bpm",
    min_value: 30,
    max_value: 120,
    allowed_sources: ["manual", "device"],
    has_recalc: false,
  },
  hrv: {
    key: "hrv",
    display_name: "HRV",
    unit: "ms",
    min_value: 5,
    max_value: 200,
    allowed_sources: ["manual", "device"],
    has_recalc: false,
  },
};

// Convert API response to MetricEntry for chart
function toMetricEntry(resp: MetricEntryResponse): MetricEntry {
  return {
    id: String(resp.id),
    effective_date: resp.effective_date,
    value: resp.value,
    source: resp.source,
    source_detail: resp.source_detail ?? undefined,
    notes: resp.notes ?? undefined,
  };
}

// Format date for display
function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Current metric card component
interface CurrentMetricCardProps {
  metricType: MetricType;
  entry: MetricEntry | null;
  onAdd: () => void;
  onClick: () => void;
}

function CurrentMetricCard({ metricType, entry, onAdd, onClick }: CurrentMetricCardProps) {
  if (!entry) {
    return (
      <div className="flex-1 p-4 text-center">
        <p className="text-metric-label mb-1">
          {metricType.display_name}
        </p>
        <p className="text-2xl font-bold text-muted-foreground mb-2"></p>
        <Button variant="outline" size="sm" onClick={onAdd}>
          Add
        </Button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex-1 p-4 text-center cursor-pointer rounded-lg transition-colors",
        "hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      tabIndex={0}
      role="button"
    >
      <p className="text-metric-label mb-1">
        {metricType.display_name}
      </p>
      <p className="text-metric">
        {entry.value} <span className="text-sm font-normal text-muted-foreground">{metricType.unit}</span>
      </p>
      <p className="text-body-secondary mt-1">
        since {formatDate(entry.effective_date)}
      </p>
    </div>
  );
}

// Loading skeleton
function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-28" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            {[1, 2].map((i) => (
              <div key={i} className="text-center p-4">
                <Skeleton className="h-3 w-16 mx-auto mb-2" />
                <Skeleton className="h-8 w-20 mx-auto mb-2" />
                <Skeleton className="h-3 w-12 mx-auto" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      {[1, 2].map((i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[200px] w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function AthleteRecovery() {
  const [loading, setLoading] = useState(true);
  const [restingHrHistory, setRestingHrHistory] = useState<MetricEntry[]>([]);
  const [hrvHistory, setHrvHistory] = useState<MetricEntry[]>([]);

  // Time range state
  const [restingHrTimeRange, setRestingHrTimeRange] = useState<TimeRange>("6M");
  const [hrvTimeRange, setHrvTimeRange] = useState<TimeRange>("6M");

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<MetricEntry | undefined>(undefined);
  const [selectedMetricKey, setSelectedMetricKey] = useState<string>("resting_hr");

  // Fetch recovery metrics
  const loadMetrics = useCallback(async () => {
    try {
      const data = await fetchMetrics({ category: "recovery" });
      
      // Group by metric type and sort by date ascending
      const restingHr: MetricEntry[] = [];
      const hrv: MetricEntry[] = [];
      
      for (const entry of data) {
        const converted = toMetricEntry(entry);
        switch (entry.metric_type) {
          case "resting_hr": restingHr.push(converted); break;
          case "hrv": hrv.push(converted); break;
        }
      }
      
      // Sort ascending by date for charts
      const sortByDate = (a: MetricEntry, b: MetricEntry) =>
        new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime();
      
      setRestingHrHistory(restingHr.sort(sortByDate));
      setHrvHistory(hrv.sort(sortByDate));
    } catch (err) {
      console.error("Failed to load recovery metrics:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  // Get current (most recent) values
  const currentRestingHr = restingHrHistory.length > 0 ? restingHrHistory[restingHrHistory.length - 1] : null;
  const currentHrv = hrvHistory.length > 0 ? hrvHistory[hrvHistory.length - 1] : null;

  // Modal handlers
  function openAddModal(metricKey: string) {
    setSelectedMetricKey(metricKey);
    setSelectedEntry(undefined);
    setModalOpen(true);
  }

  function openEditModal(entry: MetricEntry, metricKey: string) {
    setSelectedMetricKey(metricKey);
    setSelectedEntry(entry);
    setModalOpen(true);
  }

  async function handleSave(data: MetricEntryCreate | MetricEntryUpdate) {
    try {
      if (selectedEntry) {
        const updateData = data as MetricEntryUpdate;
        await updateMetric(parseInt(selectedEntry.id), {
          value: updateData.value,
          effective_date: updateData.effective_date,
          notes: updateData.notes,
        });
      } else {
        const createData = data as MetricEntryCreate;
        await createMetric({
          metric_type: selectedMetricKey,
          effective_date: createData.effective_date,
          value: createData.value,
          source: createData.source,
          source_detail: createData.source_detail,
          notes: createData.notes,
        });
      }
      await loadMetrics();
      setModalOpen(false);
    } catch (err) {
      console.error("Failed to save metric:", err);
      throw err;
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteMetric(parseInt(id));
      await loadMetrics();
      setModalOpen(false);
    } catch (err) {
      console.error("Failed to delete metric:", err);
      throw err;
    }
  }

  const selectedMetricType = METRIC_TYPES[selectedMetricKey];
  const isLastEntry = selectedMetricKey === "resting_hr"
    ? restingHrHistory.length === 1
    : hrvHistory.length === 1;

  if (loading) {
    return <LoadingSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Current values */}
      <Card>
        <CardHeader>
          <CardTitle>Current Values</CardTitle>
          <CardAction>
            <Button variant="ghost" size="sm" onClick={() => openAddModal("resting_hr")}>
              + Add
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 divide-y sm:divide-y-0 sm:divide-x divide-border">
            <CurrentMetricCard
              metricType={METRIC_TYPES.resting_hr}
              entry={currentRestingHr}
              onAdd={() => openAddModal("resting_hr")}
              onClick={() => currentRestingHr && openEditModal(currentRestingHr, "resting_hr")}
            />
            <CurrentMetricCard
              metricType={METRIC_TYPES.hrv}
              entry={currentHrv}
              onAdd={() => openAddModal("hrv")}
              onClick={() => currentHrv && openEditModal(currentHrv, "hrv")}
            />
          </div>
        </CardContent>
      </Card>

      {/* Resting HR History */}
      <Card>
        <CardHeader>
          <CardTitle>Resting HR History</CardTitle>
          <CardAction>
            <Button variant="ghost" size="sm" onClick={() => openAddModal("resting_hr")}>
              + Add
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {restingHrHistory.length === 0 ? (
            <div className="h-[200px] flex flex-col items-center justify-center text-center">
              <p className="text-muted-foreground mb-3">No resting HR history</p>
              <Button variant="outline" size="sm" onClick={() => openAddModal("resting_hr")}>
                Add first entry
              </Button>
            </div>
          ) : (
            <MetricTimelineChart
              entries={restingHrHistory}
              chartType="line"
              unit="bpm"
              timeRange={restingHrTimeRange}
              onTimeRangeChange={setRestingHrTimeRange}
              onPointClick={(entry) => openEditModal(entry, "resting_hr")}
            />
          )}
        </CardContent>
      </Card>

      {/* HRV History */}
      <Card>
        <CardHeader>
          <CardTitle>HRV History</CardTitle>
          <CardAction>
            <Button variant="ghost" size="sm" onClick={() => openAddModal("hrv")}>
              + Add
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {hrvHistory.length === 0 ? (
            <div className="h-[200px] flex flex-col items-center justify-center text-center">
              <p className="text-muted-foreground mb-3">No HRV history</p>
              <Button variant="outline" size="sm" onClick={() => openAddModal("hrv")}>
                Add first entry
              </Button>
            </div>
          ) : (
            <MetricTimelineChart
              entries={hrvHistory}
              chartType="line"
              unit="ms"
              timeRange={hrvTimeRange}
              onTimeRangeChange={setHrvTimeRange}
              onPointClick={(entry) => openEditModal(entry, "hrv")}
            />
          )}
        </CardContent>
      </Card>

      {/* Info banner */}
      <div className="p-4 rounded-lg bg-muted/50 border border-border text-sm">
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">Recovery metrics</span>
          {" "} Resting heart rate and HRV can be synced from Garmin or entered manually. Automatic device sync coming soon.
        </p>
      </div>

      {/* Entry Modal */}
      <MetricEntryModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        metricType={selectedMetricType}
        entry={selectedEntry}
        onSave={handleSave}
        onDelete={handleDelete}
        isLastEntry={isLastEntry}
      />
    </div>
  );
}
