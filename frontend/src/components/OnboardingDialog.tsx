/**
 * OnboardingDialog — 3-step onboarding for new users.
 *
 * Step 1: Profile — DOB and weight (required)
 * Step 2: Review Thresholds — computed from profile, editable
 * Step 3: Get Data — Connect integration / Upload FIT / Skip
 *
 * DOB and weight are mandatory. Thresholds are computed using:
 * - HRmax: Tanaka formula (208 - 0.7 × age)
 * - LTHR: 93% of HRmax
 * - FTP: weight × 2.5 W/kg
 */

import { useState, useRef, useMemo } from "react";
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
import { createThreshold, updatePreferences, uploadFit } from "../api";
import { toast } from "sonner";

interface Props {
  open: boolean;
  onDone: () => void;
}

type Step = "profile" | "thresholds" | "get-data";

/**
 * Calculate age in years from a date of birth string.
 * Returns null if the DOB is invalid or in the future.
 */
function calculateAge(dob: string): number | null {
  if (!dob) return null;
  const today = new Date();
  const birthDate = new Date(dob);
  if (isNaN(birthDate.getTime()) || birthDate > today) return null;
  return Math.floor(
    (today.getTime() - birthDate.getTime()) / (365.25 * 24 * 60 * 60 * 1000)
  );
}

/**
 * Compute default thresholds from DOB and weight.
 * Mirrors backend logic in domain/thresholds.py
 */
function computeDefaultThresholds(dob: string, weightKg: number): {
  hrmax: number;
  lthr: number;
  ftp: number;
} | null {
  const age = calculateAge(dob);
  if (age === null) return null;

  // Tanaka formula for HRmax
  const hrmax = Math.round(208 - 0.7 * age);
  // LTHR is 93% of HRmax
  const lthr = Math.round(hrmax * 0.93);
  // FTP estimate: 2.5 W/kg
  const ftp = Math.round(weightKg * 2.5);

  return { hrmax, lthr, ftp };
}

export function OnboardingDialog({ open, onDone }: Props): React.JSX.Element {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("profile");

  // Step 1: Profile form state
  const [dob, setDob] = useState("");
  const [weight, setWeight] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  // Step 2: Threshold form state (initialized from computed defaults)
  const [ftp, setFtp] = useState("");
  const [lthr, setLthr] = useState("");
  const [hrmax, setHrmax] = useState("");
  const [savingThresholds, setSavingThresholds] = useState(false);

  // Step 3: File upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  // Compute default thresholds when profile is filled
  const computedDefaults = useMemo(() => {
    if (dob && weight) {
      const weightNum = parseFloat(weight);
      if (weightNum > 0) {
        return computeDefaultThresholds(dob, weightNum);
      }
    }
    return null;
  }, [dob, weight]);

  // Validation for step 1
  const isProfileValid = useMemo(() => {
    if (!dob || !weight) return false;
    const weightNum = parseFloat(weight);
    if (isNaN(weightNum) || weightNum <= 0 || weightNum > 500) return false;
    
    // Validate age is between 10-100
    const age = calculateAge(dob);
    if (age === null || age < 10 || age > 100) return false;
    
    return true;
  }, [dob, weight]);

  function handleGoToSettings() {
    onDone();
    navigate("/settings");
  }

  async function handleSaveProfile(): Promise<void> {
    if (!isProfileValid) return;
    setSavingProfile(true);
    setError(null);
    try {
      await updatePreferences({
        date_of_birth: dob,
        weight_kg: parseFloat(weight),
      });

      // Initialize threshold fields with computed defaults
      if (computedDefaults) {
        setFtp(String(computedDefaults.ftp));
        setLthr(String(computedDefaults.lthr));
        setHrmax(String(computedDefaults.hrmax));
      }

      setStep("thresholds");
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to save profile";
      setError(errorMessage);
      toast.error("Failed to save profile", {
        description: "Please check your values and try again.",
      });
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleSaveThresholds(): Promise<void> {
    setSavingThresholds(true);
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
      setStep("get-data");
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to save thresholds";
      setError(errorMessage);
      toast.error("Failed to save thresholds", {
        description: "Please check your values and try again.",
      });
    } finally {
      setSavingThresholds(false);
    }
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
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  function handleSkipData() {
    onDone();
  }

  // Reset state when dialog closes
  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) {
      setStep("profile");
      setDob("");
      setWeight("");
      setFtp("");
      setLthr("");
      setHrmax("");
      setError(null);
      onDone();
    }
  }

  // Calculate age for display
  const displayAge = useMemo(() => calculateAge(dob), [dob]);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        {step === "profile" && (
          <>
            <DialogHeader>
              <DialogTitle>Welcome to TrainDash</DialogTitle>
              <DialogDescription>
                Let's set up your profile. We need your date of birth and weight
                to calculate your training zones and metrics.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label htmlFor="ob-dob">Date of Birth</Label>
                <Input
                  id="ob-dob"
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  max={new Date().toISOString().split("T")[0]}
                />
                {displayAge !== null && (
                  <p className="text-xs text-muted-foreground">
                    Age: {displayAge} years
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ob-weight">Weight</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="ob-weight"
                    type="number"
                    min={30}
                    max={500}
                    step={0.1}
                    placeholder="e.g. 75"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    className="flex-1"
                  />
                  <span className="text-sm text-muted-foreground w-8">kg</span>
                </div>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>

            <DialogFooter>
              <Button
                onClick={handleSaveProfile}
                disabled={!isProfileValid || savingProfile}
              >
                {savingProfile ? "Saving…" : "Continue"}
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "thresholds" && (
          <>
            <DialogHeader>
              <DialogTitle>Review Your Thresholds</DialogTitle>
              <DialogDescription>
                Based on your profile, we've estimated your training thresholds.
                Adjust them if you know your actual values.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
                <p className="text-xs text-muted-foreground">
                  These are estimates based on your age and weight. They'll
                  improve automatically as you add activities.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ob-hrmax">
                  HRmax — Max Heart Rate
                  {computedDefaults && (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      (estimated from age)
                    </span>
                  )}
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="ob-hrmax"
                    type="number"
                    min={100}
                    max={250}
                    placeholder="e.g. 185"
                    value={hrmax}
                    onChange={(e) => setHrmax(e.target.value)}
                    className="flex-1"
                  />
                  <span className="text-sm text-muted-foreground w-12">bpm</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ob-lthr">
                  LTHR — Lactate Threshold Heart Rate
                  {computedDefaults && (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      (93% of HRmax)
                    </span>
                  )}
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="ob-lthr"
                    type="number"
                    min={80}
                    max={220}
                    placeholder="e.g. 162"
                    value={lthr}
                    onChange={(e) => setLthr(e.target.value)}
                    className="flex-1"
                  />
                  <span className="text-sm text-muted-foreground w-12">bpm</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ob-ftp">
                  FTP — Functional Threshold Power
                  {computedDefaults && (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      (2.5 W/kg)
                    </span>
                  )}
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="ob-ftp"
                    type="number"
                    min={50}
                    max={600}
                    placeholder="e.g. 250"
                    value={ftp}
                    onChange={(e) => setFtp(e.target.value)}
                    className="flex-1"
                  />
                  <span className="text-sm text-muted-foreground w-12">W</span>
                </div>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>

            <DialogFooter>
              <Button
                onClick={handleSaveThresholds}
                disabled={savingThresholds}
              >
                {savingThresholds ? "Saving…" : "Save & continue"}
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "get-data" && (
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
                  <svg
                    className="w-5 h-5 text-primary"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                    />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground">
                    Connect Integration
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Link Xert or Garmin to auto-sync your rides
                  </p>
                </div>
                <svg
                  className="w-5 h-5 text-muted-foreground"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </button>

              {/* Upload FIT file option */}
              <label className="w-full flex items-center gap-4 p-4 rounded-lg border border-border bg-card hover:border-primary/50 hover:bg-accent/50 transition-colors cursor-pointer">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-success/10 flex items-center justify-center">
                  <svg
                    className="w-5 h-5 text-success"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                    />
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
                  <svg
                    className="w-5 h-5 text-muted-foreground animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                ) : (
                  <svg
                    className="w-5 h-5 text-muted-foreground"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 5l7 7-7 7"
                    />
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
