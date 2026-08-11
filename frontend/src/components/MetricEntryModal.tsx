import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { MetricEntry, MetricSource } from "./MetricTimelineChart";

// Metric type definition
export interface MetricType {
  key: string;
  display_name: string;
  unit: string;
  min_value?: number;
  max_value?: number;
  allowed_sources: MetricSource[];
  has_recalc: boolean;
}

// Create/Update payloads
export interface MetricEntryCreate {
  effective_date: string;
  value: number;
  source: MetricSource;
  source_detail?: string;
  notes?: string;
}

export interface MetricEntryUpdate {
  id: string;
  effective_date?: string;
  value?: number;
  source?: MetricSource;
  source_detail?: string;
  notes?: string;
}

export interface MetricEntryModalProps {
  open: boolean;
  onClose: () => void;
  metricType: MetricType;
  entry?: MetricEntry;
  onSave: (data: MetricEntryCreate | MetricEntryUpdate) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  isLastEntry?: boolean;
}

// Alert banner for device entries
function DeviceBanner({ sourceDetail }: { sourceDetail?: string }) {
  return (
    <div className="p-3 rounded-lg bg-warning/10 border border-warning/20 text-sm">
      <p className="font-medium text-warning">Device-synced entry</p>
      <p className="text-muted-foreground mt-1">
        This entry was synced from {sourceDetail || "your device"}. It cannot be edited, but you can delete it.
      </p>
    </div>
  );
}

// Delete confirmation dialog
interface DeleteConfirmProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLastEntry: boolean;
  metricName: string;
  deleting: boolean;
}

function DeleteConfirmDialog({
  open,
  onClose,
  onConfirm,
  isLastEntry,
  metricName,
  deleting,
}: DeleteConfirmProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete entry?</DialogTitle>
          <DialogDescription>
            {isLastEntry ? (
              <span className="text-destructive">
                This is your only {metricName} entry. Deleting it will leave {metricName} undefined.
              </span>
            ) : (
              `This will permanently delete this ${metricName} entry.`
            )}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={deleting}>
            {deleting ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function MetricEntryModal({
  open,
  onClose,
  metricType,
  entry,
  onSave,
  onDelete,
  isLastEntry = false,
}: MetricEntryModalProps) {
  const isEditMode = !!entry;
  const isDeviceEntry = entry?.source === "device";

  // Form state
  const [effectiveDate, setEffectiveDate] = useState("");
  const [value, setValue] = useState("");
  const [source, setSource] = useState<MetricSource>("manual");
  const [sourceDetail, setSourceDetail] = useState("");
  const [notes, setNotes] = useState("");

  // UI state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Reset form when modal opens or entry changes
  useEffect(() => {
    if (open) {
      if (entry) {
        setEffectiveDate(entry.effective_date);
        setValue(String(entry.value));
        setSource(entry.source);
        setSourceDetail(entry.source_detail || "");
        setNotes(entry.notes || "");
      } else {
        setEffectiveDate(new Date().toISOString().split("T")[0]);
        setValue("");
        setSource(metricType.allowed_sources[0] || "manual");
        setSourceDetail("");
        setNotes("");
      }
      setError(null);
    }
  }, [open, entry, metricType.allowed_sources]);

  // Validation
  function validate(): string | null {
    if (!effectiveDate) return "Date is required";
    if (!value) return "Value is required";

    const numValue = parseFloat(value);
    if (isNaN(numValue)) return "Value must be a number";

    if (metricType.min_value !== undefined && numValue < metricType.min_value) {
      return `Value must be at least ${metricType.min_value}`;
    }
    if (metricType.max_value !== undefined && numValue > metricType.max_value) {
      return `Value must be at most ${metricType.max_value}`;
    }

    return null;
  }

  async function handleSave() {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      if (isEditMode && entry) {
        await onSave({
          id: entry.id,
          effective_date: effectiveDate,
          value: parseFloat(value),
          source,
          source_detail: sourceDetail || undefined,
          notes: notes || undefined,
        });
      } else {
        await onSave({
          effective_date: effectiveDate,
          value: parseFloat(value),
          source,
          source_detail: sourceDetail || undefined,
          notes: notes || undefined,
        });
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!entry || !onDelete) return;

    setDeleting(true);
    try {
      await onDelete(entry.id);
      setShowDeleteConfirm(false);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    } finally {
      setDeleting(false);
    }
  }

  const title = isEditMode
    ? `Edit ${metricType.display_name}`
    : `Add ${metricType.display_name}`;

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!isDeviceEntry) handleSave();
            }}
            className="space-y-4"
          >
            {isDeviceEntry && <DeviceBanner sourceDetail={sourceDetail} />}

            {/* Date field */}
            <div className="space-y-1.5">
              <Label htmlFor="effective_date">Date</Label>
              <Input
                id="effective_date"
                type="date"
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
                disabled={isDeviceEntry}
              />
            </div>

            {/* Value field */}
            <div className="space-y-1.5">
              <Label htmlFor="value">
                Value ({metricType.unit})
              </Label>
              <Input
                id="value"
                type="number"
                step="any"
                min={metricType.min_value}
                max={metricType.max_value}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={`e.g., ${metricType.min_value ?? 0}`}
                disabled={isDeviceEntry}
              />
              {(metricType.min_value !== undefined || metricType.max_value !== undefined) && (
                <p className="text-caption">
                  Range: {metricType.min_value ?? "—"} – {metricType.max_value ?? "—"} {metricType.unit}
                </p>
              )}
            </div>

            {/* Source field */}
            <div className="space-y-1.5">
              <Label htmlFor="source">Source</Label>
              <select
                id="source"
                value={source}
                onChange={(e) => setSource(e.target.value as MetricSource)}
                disabled={isDeviceEntry}
                className={cn(
                  "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors",
                  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                  "disabled:cursor-not-allowed disabled:opacity-50"
                )}
              >
                {metricType.allowed_sources.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            {/* Source detail field (conditional) */}
            {source !== "manual" && (
              <div className="space-y-1.5">
                <Label htmlFor="source_detail">Source Detail</Label>
                <Input
                  id="source_detail"
                  type="text"
                  value={sourceDetail}
                  onChange={(e) => setSourceDetail(e.target.value)}
                  placeholder="e.g., ramp_test, garmin_sync"
                  disabled={isDeviceEntry}
                />
              </div>
            )}

            {/* Notes field */}
            <div className="space-y-1.5">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Any additional context..."
                rows={2}
                disabled={isDeviceEntry}
              />
            </div>

            {/* Error display */}
            {error && (
              <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
                {error}
              </div>
            )}
          </form>

          <DialogFooter>
            {isEditMode && onDelete && (
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={saving}
                className="mr-auto text-destructive hover:text-destructive"
              >
                Delete
              </Button>
            )}
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            {!isDeviceEntry && (
              <Button type="button" onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DeleteConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDelete}
        isLastEntry={isLastEntry}
        metricName={metricType.display_name}
        deleting={deleting}
      />
    </>
  );
}
