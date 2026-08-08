import { useState } from "react";
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

// Mock VO2max history
const MOCK_VO2MAX_HISTORY: MetricEntry[] = [
  { id: "v1", effective_date: "2026-01-10", value: 48.5, source: "device", source_detail: "garmin_sync" },
  { id: "v2", effective_date: "2026-03-15", value: 50.1, source: "device", source_detail: "garmin_sync" },
  { id: "v3", effective_date: "2026-05-20", value: 51.8, source: "device", source_detail: "garmin_sync" },
  { id: "v4", effective_date: "2026-07-15", value: 52.3, source: "device", source_detail: "garmin_sync" },
];

// Format date for display
function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Source badge component
function SourceBadge({ source, detail }: { source: string; detail?: string }) {
  return (
    <span className="text-xs text-muted-foreground">
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
  // In a real implementation, these would come from API queries
  const [loading] = useState(false);
  const [vo2maxHistory, setVo2maxHistory] = useState<MetricEntry[]>(MOCK_VO2MAX_HISTORY);

  // Time range state
  const [timeRange, setTimeRange] = useState<TimeRange>("1Y");

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<MetricEntry | undefined>(undefined);

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
    const isUpdate = "id" in data;

    if (isUpdate) {
      const updateData = data as MetricEntryUpdate;
      setVo2maxHistory(
        vo2maxHistory.map((e) =>
          e.id === updateData.id
            ? { ...e, ...updateData, value: updateData.value ?? e.value }
            : e
        )
      );
    } else {
      const createData = data as MetricEntryCreate;
      const newEntry: MetricEntry = {
        id: String(Date.now()),
        effective_date: createData.effective_date,
        value: createData.value,
        source: createData.source,
        source_detail: createData.source_detail,
        notes: createData.notes,
      };
      const updated = [...vo2maxHistory, newEntry].sort(
        (a, b) => new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime()
      );
      setVo2maxHistory(updated);
    }
  }

  async function handleDelete(id: string) {
    setVo2maxHistory(vo2maxHistory.filter((e) => e.id !== id));
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
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                VO2 Max
              </p>
              <p className="text-3xl font-bold text-foreground">
                {currentVo2max.value} <span className="text-lg font-normal text-muted-foreground">ml/kg/min</span>
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                since {formatDate(currentVo2max.effective_date)} • <SourceBadge source={currentVo2max.source} detail={currentVo2max.source_detail} />
              </p>
            </div>
          ) : (
            <div className="py-8 text-center">
              <p className="text-muted-foreground mb-2">No VO2 Max data yet</p>
              <p className="text-sm text-muted-foreground mb-4">
                Add manually or sync from Garmin (coming soon)
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
          <span className="font-medium text-foreground">ℹ️ About VO2 Max</span>
          {" "}— VO2 Max estimates can be synced automatically from Garmin devices. Manual entry is also supported for data from other sources.
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
