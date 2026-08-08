import { useState } from "react";
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

// Mock user profile data
interface UserProfile {
  height_cm: number | null;
  gender: string | null;
}

const MOCK_USER_PROFILE: UserProfile = {
  height_cm: 178,
  gender: "male",
};

// Mock weight history
const MOCK_WEIGHT_HISTORY: MetricEntry[] = [
  { id: "w1", effective_date: "2026-01-05", value: 74.2, source: "manual" },
  { id: "w2", effective_date: "2026-02-01", value: 73.8, source: "device", source_detail: "garmin_scale" },
  { id: "w3", effective_date: "2026-03-15", value: 73.1, source: "manual" },
  { id: "w4", effective_date: "2026-04-20", value: 72.8, source: "device", source_detail: "garmin_scale" },
  { id: "w5", effective_date: "2026-06-01", value: 72.3, source: "manual" },
  { id: "w6", effective_date: "2026-07-15", value: 72.5, source: "device", source_detail: "garmin_scale" },
];

// Format date for display
function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Profile Edit Modal
interface ProfileEditModalProps {
  open: boolean;
  onClose: () => void;
  profile: UserProfile;
  onSave: (data: { height_cm: number | null; gender: string | null }) => Promise<void>;
}

function ProfileEditModal({ open, onClose, profile, onSave }: ProfileEditModalProps) {
  const [height, setHeight] = useState(profile.height_cm?.toString() || "");
  const [gender, setGender] = useState(profile.gender || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens
  useState(() => {
    if (open) {
      setHeight(profile.height_cm?.toString() || "");
      setGender(profile.gender || "");
      setError(null);
    }
  });

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
        gender: gender || null,
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
              value={gender}
              onChange={(e) => setGender(e.target.value)}
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

export function AthleteBody() {
  // In a real implementation, these would come from API queries
  const [loading] = useState(false);
  const [userProfile, setUserProfile] = useState<UserProfile>(MOCK_USER_PROFILE);
  const [weightHistory, setWeightHistory] = useState<MetricEntry[]>(MOCK_WEIGHT_HISTORY);

  // Time range state
  const [timeRange, setTimeRange] = useState<TimeRange>("1Y");

  // Modal state
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [weightModalOpen, setWeightModalOpen] = useState(false);
  const [selectedWeightEntry, setSelectedWeightEntry] = useState<MetricEntry | undefined>(undefined);

  // Get current weight (most recent)
  const currentWeight = weightHistory.length > 0 ? weightHistory[weightHistory.length - 1] : null;

  // Profile save handler
  async function handleProfileSave(data: { height_cm: number | null; gender: string | null }) {
    // In a real implementation, this would call the API
    setUserProfile(data);
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
    const isUpdate = "id" in data;

    if (isUpdate) {
      const updateData = data as MetricEntryUpdate;
      setWeightHistory(
        weightHistory.map((e) =>
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
      const updated = [...weightHistory, newEntry].sort(
        (a, b) => new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime()
      );
      setWeightHistory(updated);
    }
  }

  async function handleWeightDelete(id: string) {
    setWeightHistory(weightHistory.filter((e) => e.id !== id));
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
              value={userProfile.height_cm ? `${userProfile.height_cm} cm` : null}
            />
            <ProfileCard
              label="Gender"
              value={userProfile.gender ? userProfile.gender.charAt(0).toUpperCase() + userProfile.gender.slice(1) : null}
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
        profile={userProfile}
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
