/**
 * Shared "Name your segment" dialog used when approving a suggestion.
 *
 * Handles the name input, validation (3-100 chars), and approve submission
 * via `approveSuggestion`. The caller decides what happens on success.
 */

import { useEffect, useState } from "react";
import type { JSX } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import type { SegmentSuggestion } from "@/api/suggestions";
import { approveSuggestion } from "@/api/suggestions";
import { formatDistance, type UnitSystem } from "@/format";

interface SegmentNamingDialogProps {
  suggestion: SegmentSuggestion | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  unitSystem: UnitSystem;
  onCreated: (segmentId: string) => void;
}

export function SegmentNamingDialog({
  suggestion,
  open,
  onOpenChange,
  unitSystem,
  onCreated,
}: SegmentNamingDialogProps): JSX.Element | null {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setError(null);
      setSubmitting(false);
    }
  }, [open, suggestion]);

  if (!suggestion) return null;

  const submit = async (): Promise<void> => {
    setError(null);
    setSubmitting(true);
    try {
      const segment = await approveSuggestion(suggestion.id, name.trim());
      toast("Segment created");
      onOpenChange(false);
      onCreated(segment.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create segment");
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Name your segment</DialogTitle>
          <DialogDescription>
            {formatDistance(suggestion.distance_m, unitSystem)} ·{" "}
            {suggestion.avg_grade_pct.toFixed(1)}% avg grade
          </DialogDescription>
        </DialogHeader>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Segment name"
          aria-label="Segment name"
          minLength={3}
          maxLength={100}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={submitting || name.trim().length < 3}>
            {submitting ? "Creating…" : "Create Segment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
