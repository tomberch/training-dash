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

// Metric type definitions for thresholds
const METRIC_TYPES: Record<string, MetricType> = {
  ftp: {
    key: "ftp",
    display_name: "FTP",
    unit: "W",
    min_value: 50,
    max_value: 500,
    allowed_sources: ["manual", "calculated", "device"],
    has_recalc: true,
  },
  lthr: {
    key: "lthr",
    display_name: "LTHR",
    unit: "bpm",
    min_value: 80,
    max_value: 220,
    allowed_sources: ["manual", "calculated", "device"],
    has_recalc: true,
  },
  hrmax: {
    key: "hrmax",
    display_name: "HRmax",
    unit: "bpm",
    min_value: 120,
    max_value: 250,
    allowed_sources: ["manual", "calculated", "device"],
    has_recalc: true,
  },
};

// Mock data - will be replaced with API calls
const MOCK_FTP_HISTORY: MetricEntry[] = [
  { id: "1", effective_date: "2026-01-15", value: 245, source: "manual", notes: "Initial FTP test" },
  { id: "2", effective_date: "2026-03-01", value: 255, source: "calculated", source_detail: "ramp_test" },
  { id: "3", effective_date: "2026-05-10", value: 262, source: "device", source_detail: "garmin_sync" },
  { id: "4", effective_date: "2026-07-01", value: 265, source: "manual", notes: "Post training block" },
];

const MOCK_LTHR_HISTORY: MetricEntry[] = [
  { id: "10", effective_date: "2026-01-15", value: 165, source: "manual" },
  { id: "11", effective_date: "2026-06-15", value: 168, source: "calculated", source_detail: "drift_test" },
];

const MOCK_HRMAX_HISTORY: MetricEntry[] = [
  { id: "20", effective_date: "2026-01-01", value: 186, source: "manual", notes: "Field test max" },
];

// Format date for display
function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Source badge component
function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, string> = {
    manual: "bg-primary/20 text-primary",
    calculated: "bg-success/20 text-success",
    device: "bg-warning/20 text-warning",
  };

  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${colors[source] || "bg-muted text-muted-foreground"}`}>
      {source}
    </span>
  );
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
      <Card className="flex-1">
        <CardContent className="flex flex-col items-center justify-center py-6 text-center">
          <p className="text-muted-foreground mb-3">No {metricType.display_name} set</p>
          <Button variant="outline" size="sm" onClick={onAdd}>
            Add {metricType.display_name}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className="flex-1 cursor-pointer hover:bg-muted/50 transition-colors"
      onClick={onClick}
    >
      <CardContent className="py-4 text-center">
        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
          {metricType.display_name}
        </p>
        <p className="text-2xl font-bold text-foreground">
          {entry.value} {metricType.unit}
        </p>
        <p className="text-sm text-muted-foreground mt-1">
          since {formatDate(entry.effective_date)}
        </p>
        <div className="mt-2">
          <SourceBadge source={entry.source} />
        </div>
      </CardContent>
    </Card>
  );
}

// Metric history section component
interface MetricHistorySectionProps {
  metricType: MetricType;
  entries: MetricEntry[];
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
  onPointClick: (entry: MetricEntry) => void;
  onAdd: () => void;
}

function MetricHistorySection({
  metricType,
  entries,
  timeRange,
  onTimeRangeChange,
  onPointClick,
  onAdd,
}: MetricHistorySectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{metricType.display_name} History</CardTitle>
        <CardAction>
          <Button variant="ghost" size="sm" onClick={onAdd}>
            + Add
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <div className="h-[200px] flex flex-col items-center justify-center text-center">
            <p className="text-muted-foreground mb-3">No {metricType.display_name} history</p>
            <Button variant="outline" size="sm" onClick={onAdd}>
              Add first entry
            </Button>
          </div>
        ) : (
          <MetricTimelineChart
            entries={entries}
            chartType="step"
            unit={metricType.unit}
            timeRange={timeRange}
            onTimeRangeChange={onTimeRangeChange}
            onPointClick={onPointClick}
          />
        )}
      </CardContent>
    </Card>
  );
}

// Loading skeleton
function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardContent className="py-6">
              <Skeleton className="h-4 w-12 mx-auto mb-2" />
              <Skeleton className="h-8 w-20 mx-auto mb-2" />
              <Skeleton className="h-3 w-16 mx-auto" />
            </CardContent>
          </Card>
        ))}
      </div>
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-24" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[200px] w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function AthleteThresholds() {
  // In a real implementation, these would come from API queries
  const [loading] = useState(false);
  const [ftpHistory, setFtpHistory] = useState<MetricEntry[]>(MOCK_FTP_HISTORY);
  const [lthrHistory, setLthrHistory] = useState<MetricEntry[]>(MOCK_LTHR_HISTORY);
  const [hrmaxHistory, setHrmaxHistory] = useState<MetricEntry[]>(MOCK_HRMAX_HISTORY);

  // Time range state for each chart
  const [ftpTimeRange, setFtpTimeRange] = useState<TimeRange>("1Y");
  const [lthrTimeRange, setLthrTimeRange] = useState<TimeRange>("1Y");
  const [hrmaxTimeRange, setHrmaxTimeRange] = useState<TimeRange>("1Y");

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<MetricEntry | undefined>(undefined);
  const [selectedMetricKey, setSelectedMetricKey] = useState<string>("ftp");

  // Get current (most recent) values
  const currentFtp = ftpHistory.length > 0 ? ftpHistory[ftpHistory.length - 1] : null;
  const currentLthr = lthrHistory.length > 0 ? lthrHistory[lthrHistory.length - 1] : null;
  const currentHrmax = hrmaxHistory.length > 0 ? hrmaxHistory[hrmaxHistory.length - 1] : null;

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
    // In a real implementation, this would call the API
    // For now, update local state
    const isUpdate = "id" in data;
    const getHistory = () => {
      switch (selectedMetricKey) {
        case "ftp": return ftpHistory;
        case "lthr": return lthrHistory;
        case "hrmax": return hrmaxHistory;
        default: return [];
      }
    };
    const setHistory = (entries: MetricEntry[]) => {
      switch (selectedMetricKey) {
        case "ftp": setFtpHistory(entries); break;
        case "lthr": setLthrHistory(entries); break;
        case "hrmax": setHrmaxHistory(entries); break;
      }
    };

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
      // Sort by date after adding
      const updated = [...getHistory(), newEntry].sort(
        (a, b) => new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime()
      );
      setHistory(updated);
    }
  }

  async function handleDelete(id: string) {
    // In a real implementation, this would call the API
    switch (selectedMetricKey) {
      case "ftp":
        setFtpHistory(ftpHistory.filter((e) => e.id !== id));
        break;
      case "lthr":
        setLthrHistory(lthrHistory.filter((e) => e.id !== id));
        break;
      case "hrmax":
        setHrmaxHistory(hrmaxHistory.filter((e) => e.id !== id));
        break;
    }
  }

  const selectedMetricType = METRIC_TYPES[selectedMetricKey];
  const isLastEntry = (() => {
    switch (selectedMetricKey) {
      case "ftp": return ftpHistory.length === 1;
      case "lthr": return lthrHistory.length === 1;
      case "hrmax": return hrmaxHistory.length === 1;
      default: return false;
    }
  })();

  if (loading) {
    return <LoadingSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Current values */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <CurrentMetricCard
          metricType={METRIC_TYPES.ftp}
          entry={currentFtp}
          onAdd={() => openAddModal("ftp")}
          onClick={() => currentFtp && openEditModal(currentFtp, "ftp")}
        />
        <CurrentMetricCard
          metricType={METRIC_TYPES.lthr}
          entry={currentLthr}
          onAdd={() => openAddModal("lthr")}
          onClick={() => currentLthr && openEditModal(currentLthr, "lthr")}
        />
        <CurrentMetricCard
          metricType={METRIC_TYPES.hrmax}
          entry={currentHrmax}
          onAdd={() => openAddModal("hrmax")}
          onClick={() => currentHrmax && openEditModal(currentHrmax, "hrmax")}
        />
      </div>

      {/* FTP History */}
      <MetricHistorySection
        metricType={METRIC_TYPES.ftp}
        entries={ftpHistory}
        timeRange={ftpTimeRange}
        onTimeRangeChange={setFtpTimeRange}
        onPointClick={(entry) => openEditModal(entry, "ftp")}
        onAdd={() => openAddModal("ftp")}
      />

      {/* LTHR History */}
      <MetricHistorySection
        metricType={METRIC_TYPES.lthr}
        entries={lthrHistory}
        timeRange={lthrTimeRange}
        onTimeRangeChange={setLthrTimeRange}
        onPointClick={(entry) => openEditModal(entry, "lthr")}
        onAdd={() => openAddModal("lthr")}
      />

      {/* HRmax History */}
      <MetricHistorySection
        metricType={METRIC_TYPES.hrmax}
        entries={hrmaxHistory}
        timeRange={hrmaxTimeRange}
        onTimeRangeChange={setHrmaxTimeRange}
        onPointClick={(entry) => openEditModal(entry, "hrmax")}
        onAdd={() => openAddModal("hrmax")}
      />

      {/* Edit/Create Modal */}
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
