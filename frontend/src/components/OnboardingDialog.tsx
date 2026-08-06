/**
 * OnboardingDialog — shown once to new users on first login.
 *
 * Prompts for FTP, LTHR, and HRmax. All three fields are optional
 * individually (matching the backend's threshold API), but at least
 * one must be filled before the form can be submitted. Users can also
 * skip and set thresholds later in Settings.
 */

import { useState } from "react";
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
import { createThreshold } from "../api";

interface Props {
  open: boolean;
  onDone: () => void;
}

export function OnboardingDialog({ open, onDone }: Props): React.JSX.Element {
  const [ftp, setFtp] = useState("");
  const [lthr, setLthr] = useState("");
  const [hrmax, setHrmax] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasAnyValue = ftp !== "" || lthr !== "" || hrmax !== "";

  async function handleSave(): Promise<void> {
    if (!hasAnyValue) return;
    setSaving(true);
    setError(null);
    try {
      await createThreshold({
        ftp_watts: ftp !== "" ? parseInt(ftp, 10) : undefined,
        lthr_bpm: lthr !== "" ? parseInt(lthr, 10) : undefined,
        hrmax_bpm: hrmax !== "" ? parseInt(hrmax, 10) : undefined,
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save thresholds");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onDone(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Welcome — set your training thresholds</DialogTitle>
          <DialogDescription>
            TrainDash uses FTP, LTHR, and HRmax to calculate zone times, TSS,
            and intensity factor. You can skip this and add them later in
            Settings → Thresholds.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="ob-ftp">FTP — Functional Threshold Power</Label>
            <Input
              id="ob-ftp"
              type="number"
              min={50}
              max={600}
              placeholder="e.g. 250 W"
              value={ftp}
              onChange={(e) => setFtp(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              The highest average power you can sustain for ~1 hour (watts).
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ob-lthr">LTHR — Lactate Threshold Heart Rate</Label>
            <Input
              id="ob-lthr"
              type="number"
              min={80}
              max={220}
              placeholder="e.g. 162 bpm"
              value={lthr}
              onChange={(e) => setLthr(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Your heart rate at lactate threshold — roughly your 1-hour race HR.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ob-hrmax">Max Heart Rate</Label>
            <Input
              id="ob-hrmax"
              type="number"
              min={100}
              max={250}
              placeholder="e.g. 185 bpm"
              value={hrmax}
              onChange={(e) => setHrmax(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Your highest recorded heart rate (bpm).
            </p>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={onDone} disabled={saving}>
            Skip for now
          </Button>
          <Button
            onClick={handleSave}
            disabled={!hasAnyValue || saving}
          >
            {saving ? "Saving…" : "Save thresholds"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
