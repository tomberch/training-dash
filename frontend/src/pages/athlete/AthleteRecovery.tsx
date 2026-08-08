import { useState } from "react";
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

// Mock data
const MOCK_RESTING_HR_HISTORY: MetricEntry[] = [
  { id: "rhr1", effective_date: "2026-06-01", value: 54, source: "device", source_detail: "garmin_sync" },
  { id: "rhr2", effective_date: "2026-06-15", value: 53, source: "device", source_detail: "garmin_sync" },
  { id: "rhr3", effective_date: "2026-07-01", value: 52, source: "device", source_detail: "garmin_sync" },
  { id: "rhr4", effective_date: "2026-07-15", value: 51, source: "device", source_detail: "garmin_sync" },
  { id: "rhr5", effective_date: "2026-08-01", value: 52, source: "device", source_detail: "garmin_sync" },
];

const MOCK_HRV_HISTORY: MetricEntry[] = [
  { id: "hrv1", effective_date: "2026-06-01", value: 58, source: "device", source_detail: "garmin_sync" },
  { id: "hrv2", effective_date: "2026-06-15", value: 62, source: "device", source_detail: "garmin_sync" },
  { id: "hrv3", effective_date: "2026-07-01", value: 60, source: "device", source_detail: "garmin_sync" },
  { id: "hrv4", effective_date: "2026-07-15", value: 64, source: "device", source_detail: "garmin_sync" },
  { id: "hrv5", effective_date: "2026-08-01", value: 65, source: "device", source_detail: "garmin_sync" },
];

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
        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
          {metricType.display_name}
        </p>
        <p className="text-2xl font-bold text-muted-foreground mb-2">—</p>
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
      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
        {metricType.display_name}
      </p>
      <p className="text-2xl font-bold text-foreground">
        {entry.value} <span className="text-sm font-normal text-muted-foreground">{metricType.unit}</span>
      </p>
      <p className="text-sm text-muted-foreground mt-1">
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
  // In a real implementation, these would come from API queries
  const [loading] = useState(false);
  const [restingHrHistory, setRestingHrHistory] = useState<MetricEntry[]>(MOCK_RESTING_HR_HISTORY);
  const [hrvHistory, setHrvHistory] = useState<MetricEntry[]>(MOCK_HRV_HISTORY);

  // Time range state
  const [restingHrTimeRange, setRestingHrTimeRange] = useState<TimeRange>("6M");
  const [hrvTimeRange, setHrvTimeRange] = useState<TimeRange>("6M");

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<MetricEntry | undefined>(undefined);
  const [selectedMetricKey, setSelectedMetricKey] = useState<string>("resting_hr");

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
    const isUpdate = "id" in data;
    const getHistory = () => selectedMetricKey === "resting_hr" ? restingHrHistory : hrvHistory;
    const setHistory = selectedMetricKey === "resting_hr" ? setRestingHrHistory : setHrvHistory;

    if (isUpdate) {
      const updateData = data as MetricEntryUpdate;
      setHistory(
        getHistory().map((e) =>
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
      const updated = [...getHistory(), newEntry].sort(
        (a, b) => new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime()
      );
      setHistory(updated);
    }
  }

  async function handleDelete(id: string) {
    if (selectedMetricKey === "resting_hr") {
      setRestingHrHistory(restingHrHistory.filter((e) => e.id !== id));
    } else {
      setHrvHistory(hrvHistory.filter((e) => e.id !== id));
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
          <span className="font-medium text-foreground">ℹ️ Recovery metrics</span>
          {" "}— Resting heart rate and HRV can be synced from Garmin or entered manually. Automatic device sync coming soon.
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
