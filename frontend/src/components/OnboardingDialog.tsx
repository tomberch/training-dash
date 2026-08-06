/**
 * OnboardingDialog — 2-step onboarding for new users.
 *
 * Step 1: Set Thresholds — FTP, LTHR, HRmax (optional)
 * Step 2: Get Data — Connect Xert / Upload FIT / Skip
 *
 * Users can skip either step. Re-shows next login until user has
 * thresholds OR activities.
 */

import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
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
import { createThreshold, uploadFit } from "../api";
import { toast } from "sonner";

interface Props {
  open: boolean;
  onDone: () => void;
}

type Step = "set-thresholds" | "get-data";

export function OnboardingDialog({ open, onDone }: Props): React.JSX.Element {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("set-thresholds");
  
  // Step 1: Threshold form state
  const [ftp, setFtp] = useState("");
  const [lthr, setLthr] = useState("");
  const [hrmax, setHrmax] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // File upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const hasAnyValue = ftp !== "" || lthr !== "" || hrmax !== "";

  function handleGoToSettings() {
    onDone();
    navigate("/settings");
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setUploading(true);
    setError(null);
    try {
      await uploadFit(file);
      toast.success("Activity uploaded!", {
        description: "Your first ride has been imported.",
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload file");
      toast.error("Upload failed", {
        description: err instanceof Error ? err.message : "Please try again",
      });
    } finally {
      setUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleSaveThresholds(): Promise<void> {
    if (!hasAnyValue) return;
    setSaving(true);
    setError(null);
    try {
      await createThreshold({
        ftp_watts: ftp !== "" ? parseInt(ftp, 10) : undefined,
        lthr_bpm: lthr !== "" ? parseInt(lthr, 10) : undefined,
        hrmax_bpm: hrmax !== "" ? parseInt(hrmax, 10) : undefined,
      });
      toast.success("Thresholds saved!", {
        description: "Your training zones are now configured.",
      });
      // Advance to step 2: get data
      setStep("get-data");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to save thresholds";
      setError(errorMessage);
      toast.error("Failed to save thresholds", {
        description: "Please check your values and try again.",
      });
    } finally {
      setSaving(false);
    }
  }

  function handleSkipThresholds() {
    setStep("get-data");
  }

  function handleSkipData() {
    onDone();
  }

  // Reset state when dialog closes
  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) {
      setStep("set-thresholds");
      setFtp("");
      setLthr("");
      setHrmax("");
      setError(null);
      onDone();
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        {step === "set-thresholds" ? (
          <>
            <DialogHeader>
              <DialogTitle>Welcome to TrainDash</DialogTitle>
              <DialogDescription>
                Let's set up your training thresholds. TrainDash uses FTP, LTHR,
                and HRmax to calculate zone times, TSS, and intensity factor.
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
              <Button variant="ghost" onClick={handleSkipThresholds} disabled={saving}>
                Skip for now
              </Button>
              <Button
                onClick={handleSaveThresholds}
                disabled={!hasAnyValue || saving}
              >
                {saving ? "Saving…" : "Save & continue"}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Get Your Training Data</DialogTitle>
              <DialogDescription>
                Connect an integration or upload a FIT file to start analyzing
                your rides. You can also do this later in Settings.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-4">
              {/* Connect Xert/Garmin option */}
              <button
                onClick={handleGoToSettings}
                className="w-full flex items-center gap-4 p-4 rounded-lg border border-border bg-card hover:border-primary/50 hover:bg-accent/50 transition-colors text-left"
              >
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground">Connect Integration</p>
                  <p className="text-sm text-muted-foreground">
                    Link Xert or Garmin to auto-sync your rides
                  </p>
                </div>
                <svg className="w-5 h-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* Upload FIT file option */}
              <label className="w-full flex items-center gap-4 p-4 rounded-lg border border-border bg-card hover:border-primary/50 hover:bg-accent/50 transition-colors cursor-pointer">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-success/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground">
                    {uploading ? "Uploading…" : "Upload FIT File"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Import a ride from your device
                  </p>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".fit"
                  onChange={handleFileUpload}
                  disabled={uploading}
                  className="sr-only"
                />
                {uploading ? (
                  <svg className="w-5 h-5 text-muted-foreground animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </label>

              {error && (
                <p className="text-sm text-destructive px-1">{error}</p>
              )}
            </div>

            <DialogFooter>
              <Button variant="ghost" onClick={handleSkipData}>
                Skip for now
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
