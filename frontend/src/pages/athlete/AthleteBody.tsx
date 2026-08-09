import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
  updatePreferences,
  type MetricEntryResponse,
  type User,
} from "@/api";

// Weight metric type definition
const WEIGHT_METRIC_TYPE: MetricType = {
  key: "weight_kg",
  display_name: "Weight",
  unit: "kg",
  min_value: 30,
  max_value: 200,
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

// Profile Edit Modal
interface ProfileEditModalProps {
  open: boolean;
  onClose: () => void;
  heightCm: number | null;
  gender: "male" | "female" | null;
  onSave: (data: { height_cm: number | null; gender: "male" | "female" | null }) => Promise<void>;
}

function ProfileEditModal({ open, onClose, heightCm, gender, onSave }: ProfileEditModalProps) {
  const [height, setHeight] = useState(heightCm?.toString() || "");
  const [genderValue, setGenderValue] = useState<string>(gender || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setHeight(heightCm?.toString() || "");
      setGenderValue(gender || "");
      setError(null);
    }
  }, [open, heightCm, gender]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    
    const heightNum = height ? parseInt(height) : null;
    if (heightNum !== null && (heightNum < 100 || heightNum > 250)) {
      setError("Height must be between 100 and 250 cm");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await onSave({
        height_cm: heightNum,
        gender: (genderValue as "male" | "female") || null,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Profile</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="height">Height (cm)</Label>
            <Input
              id="height"
              type="number"
              min={100}
              max={250}
              value={height}
              onChange={(e) => setHeight(e.target.value)}
              placeholder="e.g., 175"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="gender">Gender</Label>
            <select
              id="gender"
              value={genderValue}
              onChange={(e) => setGenderValue(e.target.value)}
              className={cn(
                "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              )}
            >
              <option value="">Not specified</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// Profile card component
interface ProfileCardProps {
  label: string;
  value: string | null;
  subtext?: string;
}

function ProfileCard({ label, value, subtext }: ProfileCardProps) {
  return (
    <div className="text-center p-4">
      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
        {label}
      </p>
      <p className="text-2xl font-bold text-foreground">
        {value || "—"}
      </p>
      {subtext && (
        <p className="text-sm text-muted-foreground mt-1">{subtext}</p>
      )}
    </div>
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
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="text-center p-4">
                <Skeleton className="h-3 w-12 mx-auto mb-2" />
                <Skeleton className="h-8 w-16 mx-auto" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-28" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[200px] w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

interface AthleteBodyProps {
  user: User;
  onUserUpdate: (user: User) => void;
}

export function AthleteBody({ user, onUserUpdate }: AthleteBodyProps) {
  const [loading, setLoading] = useState(true);
  const [weightHistory, setWeightHistory] = useState<MetricEntry[]>([]);

  // Time range state
  const [timeRange, setTimeRange] = useState<TimeRange>("1Y");

  // Modal state
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [weightModalOpen, setWeightModalOpen] = useState(false);
  const [selectedWeightEntry, setSelectedWeightEntry] = useState<MetricEntry | undefined>(undefined);

  // Fetch weight history
  const loadWeightHistory = useCallback(async () => {
    try {
      const data = await fetchMetrics({ metric_type: "weight_kg" });
      const entries = data.map(toMetricEntry).sort(
        (a, b) => new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime()
      );
      setWeightHistory(entries);
    } catch (err) {
      console.error("Failed to load weight history:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWeightHistory();
  }, [loadWeightHistory]);

  // Get current weight (most recent)
  const currentWeight = weightHistory.length > 0 ? weightHistory[weightHistory.length - 1] : null;

  // Profile save handler
  async function handleProfileSave(data: { height_cm: number | null; gender: "male" | "female" | null }) {
    const updated = await updatePreferences({
      height_cm: data.height_cm ?? undefined,
      gender: data.gender,
    });
    onUserUpdate(updated);
  }

  // Weight modal handlers
  function openAddWeightModal() {
    setSelectedWeightEntry(undefined);
    setWeightModalOpen(true);
  }

  function openEditWeightModal(entry: MetricEntry) {
    setSelectedWeightEntry(entry);
    setWeightModalOpen(true);
  }

  async function handleWeightSave(data: MetricEntryCreate | MetricEntryUpdate) {
    try {
      if (selectedWeightEntry) {
        const updateData = data as MetricEntryUpdate;
        await updateMetric(parseInt(selectedWeightEntry.id), {
          value: updateData.value,
          effective_date: updateData.effective_date,
          notes: updateData.notes,
        });
      } else {
        const createData = data as MetricEntryCreate;
        await createMetric({
          metric_type: "weight_kg",
          effective_date: createData.effective_date,
          value: createData.value,
          source: createData.source,
          source_detail: createData.source_detail,
          notes: createData.notes,
        });
      }
      await loadWeightHistory();
      setWeightModalOpen(false);
    } catch (err) {
      console.error("Failed to save weight:", err);
      throw err;
    }
  }

  async function handleWeightDelete(id: string) {
    try {
      await deleteMetric(parseInt(id));
      await loadWeightHistory();
      setWeightModalOpen(false);
    } catch (err) {
      console.error("Failed to delete weight:", err);
      throw err;
    }
  }

  if (loading) {
    return <LoadingSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Profile section */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardAction>
            <Button variant="outline" size="sm" onClick={() => setProfileModalOpen(true)}>
              Edit
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 divide-y sm:divide-y-0 sm:divide-x divide-border">
            <ProfileCard
              label="Height"
              value={user.height_cm ? `${user.height_cm} cm` : null}
            />
            <ProfileCard
              label="Gender"
              value={user.gender ? user.gender.charAt(0).toUpperCase() + user.gender.slice(1) : null}
            />
            <ProfileCard
              label="Weight"
              value={currentWeight ? `${currentWeight.value} kg` : null}
              subtext={currentWeight ? `since ${formatDate(currentWeight.effective_date)}` : undefined}
            />
          </div>
        </CardContent>
      </Card>

      {/* Weight History */}
      <Card>
        <CardHeader>
          <CardTitle>Weight History</CardTitle>
          <CardAction>
            <Button variant="ghost" size="sm" onClick={openAddWeightModal}>
              + Add
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {weightHistory.length === 0 ? (
            <div className="h-[200px] flex flex-col items-center justify-center text-center">
              <p className="text-muted-foreground mb-3">No weight history</p>
              <Button variant="outline" size="sm" onClick={openAddWeightModal}>
                Add first entry
              </Button>
            </div>
          ) : (
            <MetricTimelineChart
              entries={weightHistory}
              chartType="line"
              unit="kg"
              timeRange={timeRange}
              onTimeRangeChange={setTimeRange}
              onPointClick={openEditWeightModal}
            />
          )}
        </CardContent>
      </Card>

      {/* Profile Edit Modal */}
      <ProfileEditModal
        open={profileModalOpen}
        onClose={() => setProfileModalOpen(false)}
        heightCm={user.height_cm}
        gender={user.gender}
        onSave={handleProfileSave}
      />

      {/* Weight Entry Modal */}
      <MetricEntryModal
        open={weightModalOpen}
        onClose={() => setWeightModalOpen(false)}
        metricType={WEIGHT_METRIC_TYPE}
        entry={selectedWeightEntry}
        onSave={handleWeightSave}
        onDelete={handleWeightDelete}
        isLastEntry={weightHistory.length === 1}
      />
    </div>
  );
}
