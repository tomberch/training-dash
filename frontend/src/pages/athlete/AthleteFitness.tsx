import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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

// VO2max metric type definition
const VO2MAX_METRIC_TYPE: MetricType = {
  key: "vo2max",
  display_name: "VO2 Max",
  unit: "ml/kg/min",
  min_value: 20,
  max_value: 90,
  allowed_sources: ["manual", "device"],
  has_recalc: false,
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

// Source badge component
function SourceBadge({ source, detail }: { source: string; detail?: string }) {
  return (
    <span className="text-caption">
      via {detail || source}
    </span>
  );
}

// Loading skeleton
function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-16" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[200px] w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

export function AthleteFitness() {
  const [loading, setLoading] = useState(true);
  const [vo2maxHistory, setVo2maxHistory] = useState<MetricEntry[]>([]);

  // Time range state
  const [timeRange, setTimeRange] = useState<TimeRange>("1Y");

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<MetricEntry | undefined>(undefined);

  // Fetch VO2max history
  const loadHistory = useCallback(async () => {
    try {
      const data = await fetchMetrics({ metric_type: "vo2max" });
      const entries = data.map(toMetricEntry).sort(
        (a, b) => new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime()
      );
      setVo2maxHistory(entries);
    } catch (err) {
      console.error("Failed to load VO2max history:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Get current (most recent) value
  const currentVo2max = vo2maxHistory.length > 0 ? vo2maxHistory[vo2maxHistory.length - 1] : null;

  // Modal handlers
  function openAddModal() {
    setSelectedEntry(undefined);
    setModalOpen(true);
  }

  function openEditModal(entry: MetricEntry) {
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
          metric_type: "vo2max",
          effective_date: createData.effective_date,
          value: createData.value,
          source: createData.source,
          source_detail: createData.source_detail,
          notes: createData.notes,
        });
      }
      await loadHistory();
      setModalOpen(false);
    } catch (err) {
      console.error("Failed to save VO2max:", err);
      throw err;
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteMetric(parseInt(id));
      await loadHistory();
      setModalOpen(false);
    } catch (err) {
      console.error("Failed to delete VO2max:", err);
      throw err;
    }
  }

  if (loading) {
    return <LoadingSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Current value */}
      <Card>
        <CardHeader>
          <CardTitle>Current</CardTitle>
          <CardAction>
            <Button variant="ghost" size="sm" onClick={openAddModal}>
              + Add
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {currentVo2max ? (
            <div
              className="p-4 rounded-lg bg-muted/50 cursor-pointer hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => openEditModal(currentVo2max)}
              onKeyDown={(e) => e.key === "Enter" && openEditModal(currentVo2max)}
              tabIndex={0}
              role="button"
            >
              <p className="text-metric-label mb-1">
                VO2 Max
              </p>
              <p className="text-3xl font-bold text-foreground">
                {currentVo2max.value} <span className="text-lg font-normal text-muted-foreground">ml/kg/min</span>
              </p>
              <p className="text-body-secondary mt-2">
                since {formatDate(currentVo2max.effective_date)} • <SourceBadge source={currentVo2max.source} detail={currentVo2max.source_detail} />
              </p>
            </div>
          ) : (
            <div className="py-8 text-center">
              <p className="text-muted-foreground mb-2">No VO2 Max data yet</p>
              <p className="text-body-secondary mb-4">
                Add manually or import from Garmin (coming soon)
              </p>
              <Button variant="outline" onClick={openAddModal}>
                Add VO2 Max
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* History chart */}
      <Card>
        <CardHeader>
          <CardTitle>VO2 Max History</CardTitle>
        </CardHeader>
        <CardContent>
          {vo2maxHistory.length === 0 ? (
            <div className="h-[200px] flex flex-col items-center justify-center text-center">
              <p className="text-muted-foreground mb-3">No history yet</p>
              <Button variant="outline" size="sm" onClick={openAddModal}>
                Add first entry
              </Button>
            </div>
          ) : (
            <MetricTimelineChart
              entries={vo2maxHistory}
              chartType="line"
              unit="ml/kg/min"
              timeRange={timeRange}
              onTimeRangeChange={setTimeRange}
              onPointClick={openEditModal}
            />
          )}
        </CardContent>
      </Card>

      {/* Info banner */}
      <div className="p-4 rounded-lg bg-muted/50 border border-border text-sm">
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">About VO2 Max</span>
          {" "} VO2 Max estimates can be synced automatically from Garmin devices. Manual entry is also supported for data from other sources.
        </p>
      </div>

      {/* Entry Modal */}
      <MetricEntryModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        metricType={VO2MAX_METRIC_TYPE}
        entry={selectedEntry}
        onSave={handleSave}
        onDelete={handleDelete}
        isLastEntry={vo2maxHistory.length === 1}
      />
    </div>
  );
}
