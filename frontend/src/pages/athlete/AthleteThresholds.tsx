import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  MetricTimelineChart,
  type MetricEntry,
  type TimeRange,
} from "@/components/MetricTimelineChart";
import { cn } from "@/lib/utils";
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
import { notifySuccess, notifyError } from "@/lib/notify";

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
function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, string> = {
    manual: "bg-primary/20 text-primary",
    calculated: "bg-success/20 text-success",
    device: "bg-warning/20 text-warning",
  };

  return (
    <span className={cn(
      "px-2 py-0.5 text-xs font-medium rounded-full",
      colors[source] || "bg-muted text-muted-foreground"
    )}>
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
      className="flex-1 cursor-pointer hover:bg-muted/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      tabIndex={0}
      role="button"
    >
      <CardContent className="py-4 text-center">
        <p className="text-metric-label mb-1">
          {metricType.display_name}
        </p>
        <p className="text-metric">
          {entry.value} {metricType.unit}
        </p>
        <p className="text-body-secondary mt-1">
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
  const [loading, setLoading] = useState(true);
  const [ftpHistory, setFtpHistory] = useState<MetricEntry[]>([]);
  const [lthrHistory, setLthrHistory] = useState<MetricEntry[]>([]);
  const [hrmaxHistory, setHrmaxHistory] = useState<MetricEntry[]>([]);

  // Time range state for each chart
  const [ftpTimeRange, setFtpTimeRange] = useState<TimeRange>("1Y");
  const [lthrTimeRange, setLthrTimeRange] = useState<TimeRange>("1Y");
  const [hrmaxTimeRange, setHrmaxTimeRange] = useState<TimeRange>("1Y");

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<MetricEntry | undefined>(undefined);
  const [selectedMetricKey, setSelectedMetricKey] = useState<string>("ftp");

  // Fetch all threshold metrics
  const loadMetrics = useCallback(async () => {
    try {
      const data = await fetchMetrics({ category: "threshold" });
      
      // Group by metric type and sort by date ascending
      const ftp: MetricEntry[] = [];
      const lthr: MetricEntry[] = [];
      const hrmax: MetricEntry[] = [];
      
      for (const entry of data) {
        const converted = toMetricEntry(entry);
        switch (entry.metric_type) {
          case "ftp": ftp.push(converted); break;
          case "lthr": lthr.push(converted); break;
          case "hrmax": hrmax.push(converted); break;
        }
      }
      
      // Sort ascending by date for charts
      const sortByDate = (a: MetricEntry, b: MetricEntry) =>
        new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime();
      
      setFtpHistory(ftp.sort(sortByDate));
      setLthrHistory(lthr.sort(sortByDate));
      setHrmaxHistory(hrmax.sort(sortByDate));
    } catch (err) {
      console.error("Failed to load threshold metrics:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

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
    const metricName = METRIC_TYPES[selectedMetricKey]?.display_name || selectedMetricKey;
    try {
      if (selectedEntry) {
        // Update existing entry
        const updateData = data as MetricEntryUpdate;
        await updateMetric(parseInt(selectedEntry.id), {
          value: updateData.value,
          effective_date: updateData.effective_date,
          notes: updateData.notes,
        });
        notifySuccess(`${metricName} updated`, {
          bellType: "threshold_saved",
        });
      } else {
        // Create new entry
        const createData = data as MetricEntryCreate;
        await createMetric({
          metric_type: selectedMetricKey,
          effective_date: createData.effective_date,
          value: createData.value,
          source: createData.source,
          source_detail: createData.source_detail,
          notes: createData.notes,
        });
        notifySuccess(`${metricName} saved`, {
          bellType: "threshold_saved",
        });
      }
      // Reload metrics after save
      await loadMetrics();
      setModalOpen(false);
    } catch (err) {
      console.error("Failed to save metric:", err);
      notifyError(`Failed to save ${metricName}`, {
        bellType: "threshold_save_failed",
      });
      throw err; // Let modal handle the error
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
