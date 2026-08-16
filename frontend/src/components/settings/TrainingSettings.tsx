import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import type { User } from "@/api";
import { updatePreferences, fetchCurrentMetrics, ApiError } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent, CardAction } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  DEFAULT_POWER_ZONES,
  DEFAULT_HR_ZONES,
  computePowerZones,
  computeHrZones,
  type ZonePercentages,
} from "@/lib/zones";
import { POWER_ZONE_COLORS, HR_ZONE_COLORS } from "@/constants";
import { FeedbackAlert } from "./FeedbackAlert";

interface TrainingSettingsProps {
  user: User;
  onUserUpdate: (user: User) => void;
}

export function TrainingSettings({ user, onUserUpdate }: TrainingSettingsProps) {
  return (
    <div className="space-y-6">
      <PowerHeartRateSection user={user} onUserUpdate={onUserUpdate} />
      <ThresholdsSection />
      <ZonesSection user={user} onUserUpdate={onUserUpdate} />
    </div>
  );
}

function PowerHeartRateSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const hrPowerModel = user.hr_power_model;
  const minRidesRequired = 5;
  const rideCount = hrPowerModel?.ride_count ?? 0;
  const modelReady = rideCount >= minRidesRequired;
  const isEnabled = user.hr_derived_power_enabled;

  async function handleToggle() {
    if (!modelReady) return;
    
    const newValue = !isEnabled;
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ hr_derived_power_enabled: newValue });
      onUserUpdate(updated);
      setFeedback({ 
        type: "success", 
        message: newValue ? "HR-derived power enabled" : "HR-derived power disabled" 
      });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to update setting";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }


  const confidencePercent = hrPowerModel?.confidence 
    ? Math.round(hrPowerModel.confidence * 100) 
    : null;

  const confidenceLabel = confidencePercent !== null
    ? confidencePercent >= 80 ? "High" : confidencePercent >= 60 ? "Medium" : "Low"
    : null;

  return (
    <Card id="power-heart-rate" className="card-hover">
      <CardHeader>
        <div className="flex items-center justify-between w-full">
          <CardTitle className="flex items-center gap-2 text-card-title">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
            Power & Heart Rate
          </CardTitle>
          <button
            onClick={handleToggle}
            disabled={saving || !modelReady}
            aria-pressed={isEnabled}
            className={cn(
              "relative inline-flex h-6 w-12 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
              isEnabled ? "bg-primary" : "bg-muted",
              (!modelReady || saving) && "opacity-50 cursor-not-allowed"
            )}
          >
            <span
              className={cn(
                "pointer-events-none absolute left-1 bottom-1 w-4 h-4 transform rounded-full bg-muted-foreground shadow transition duration-200 ease-in-out",
                isEnabled ? "translate-x-6 bg-white" : "translate-x-0"
              )}
            />
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <div>
          <h3 className="font-medium mb-2">HR-Derived Power</h3>
          <p className="text-body-secondary mb-4">
            Estimate power from heart rate on activities without a power meter.
            Uses an Efficiency Factor model trained from your dual-sensor rides.
          </p>
          
          {!modelReady && (
            <div className="bg-primary/10 border border-primary/30 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm text-foreground mb-1">Requirement not met</p>
                  <p className="text-caption">
                    Record {minRidesRequired - rideCount} more {minRidesRequired - rideCount === 1 ? "activity" : "activities"} with both power meter and heart rate to enable this feature.
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-primary rounded-full transition-all" 
                        style={{ width: `${(rideCount / minRidesRequired) * 100}%` }}
                      />
                    </div>
                    <span className="text-caption">{rideCount}/{minRidesRequired}</span>
                  </div>
                </div>
              </div>
            </div>
          )}


          {modelReady && hrPowerModel?.model_exists && (
            <div className="p-3 rounded-lg bg-muted/50 text-sm">
              <div className="flex items-center gap-4 text-muted-foreground">
                <span>Model trained on <span className="font-medium text-foreground">{rideCount}</span> rides</span>
                {confidenceLabel && (
                  <span className={cn(
                    "px-2 py-0.5 rounded-full text-xs font-medium",
                    confidencePercent && confidencePercent >= 80 
                      ? "bg-success/20 text-success" 
                      : confidencePercent && confidencePercent >= 60
                        ? "bg-warning/20 text-warning"
                        : "bg-muted text-muted-foreground"
                  )}>
                    {confidenceLabel} confidence
                  </span>
                )}
              </div>
              {hrPowerModel.is_stale && (
                <p className="text-warning mt-2 text-xs">
                  Model may be outdated. Record new dual-sensor activities to improve accuracy.
                </p>
              )}
            </div>
          )}
        </div>
        
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}

function ThresholdsSection() {
  const [metrics, setMetrics] = useState<{
    ftp: number | null;
    lthr: number | null;
    hrmax: number | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCurrentMetrics()
      .then((data) => {
        setMetrics({
          ftp: data.ftp?.value ?? null,
          lthr: data.lthr?.value ?? null,
          hrmax: data.hrmax?.value ?? null,
        });
      })
      .catch(() => {
        setMetrics(null);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Thresholds
        </CardTitle>
        <CardAction>
          <Link
            to="/athlete"
            className="inline-flex items-center gap-1 text-primary hover:text-primary/80 text-sm font-medium"
          >
            Edit on Athlete Page
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="grid grid-cols-3 gap-4 max-w-2xl">
            {[1, 2, 3].map((i) => (
              <div key={i} className="p-4 bg-muted rounded-lg">
                <Skeleton className="h-4 w-12 mb-2" />
                <Skeleton className="h-8 w-20" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4 max-w-2xl">
            <div className="p-4 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">FTP</div>
              <div className="text-2xl font-bold text-foreground">
                {metrics?.ftp ? `${metrics.ftp} W` : "—"}
              </div>
            </div>
            <div className="p-4 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">LTHR</div>
              <div className="text-2xl font-bold text-foreground">
                {metrics?.lthr ? `${metrics.lthr} bpm` : "—"}
              </div>
            </div>
            <div className="p-4 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">Max HR</div>
              <div className="text-2xl font-bold text-foreground">
                {metrics?.hrmax ? `${metrics.hrmax} bpm` : "—"}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}



function ZonesSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const [ftp, setFtp] = useState<number | null>(null);
  const [lthr, setLthr] = useState<number | null>(null);
  const [loadingThresholds, setLoadingThresholds] = useState(true);
  
  const loadThresholds = useCallback(async () => {
    try {
      const currentMetrics = await fetchCurrentMetrics();
      setFtp(currentMetrics.ftp?.value ?? null);
      setLthr(currentMetrics.lthr?.value ?? null);
    } catch (err) {
      console.error("Failed to load thresholds:", err);
    } finally {
      setLoadingThresholds(false);
    }
  }, []);
  
  useEffect(() => {
    loadThresholds();
  }, [loadThresholds]);

  const powerPercentages = user.power_zone_percentages ?? DEFAULT_POWER_ZONES;
  const hrPercentages = user.hr_zone_percentages ?? DEFAULT_HR_ZONES;
  const powerZones = computePowerZones(ftp ?? 0, powerPercentages);
  const hrZones = computeHrZones(lthr ?? 0, hrPercentages);
  const hasFtp = ftp !== null && ftp > 0;
  const hasLthr = lthr !== null && lthr > 0;

  if (loadingThresholds) {
    return (
      <>
        <Card className="card-hover">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-card-title">
              <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Power Zones
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[200px] w-full" />
          </CardContent>
        </Card>
        <Card className="card-hover">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-card-title">
              <svg className="w-5 h-5 text-pink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
              Heart Rate Zones
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[200px] w-full" />
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <>
      <PowerZonesCard 
        user={user} 
        onUserUpdate={onUserUpdate} 
        powerZones={powerZones} 
        powerPercentages={powerPercentages}
        hasFtp={hasFtp}
        ftp={ftp}
      />
      <HrZonesCard 
        user={user} 
        onUserUpdate={onUserUpdate} 
        hrZones={hrZones}
        hrPercentages={hrPercentages}
        hasLthr={hasLthr}
        lthr={lthr}
      />
    </>
  );
}



function PowerZonesCard({ 
  user: _user, 
  onUserUpdate, 
  powerZones,
  powerPercentages,
  hasFtp,
  ftp,
}: { 
  user: User; 
  onUserUpdate: (user: User) => void;
  powerZones: ReturnType<typeof computePowerZones>;
  powerPercentages: ZonePercentages;
  hasFtp: boolean;
  ftp: number | null;
}) {
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [editedPowerPct, setEditedPowerPct] = useState<ZonePercentages>(powerPercentages);
  
  const displayZones = editMode ? computePowerZones(ftp ?? 0, editedPowerPct) : powerZones;
  
  function startEdit() {
    setEditedPowerPct({ ...powerPercentages });
    setEditMode(true);
    setFeedback(null);
  }
  
  function cancelEdit() {
    setEditMode(false);
    setFeedback(null);
  }
  
  async function handleSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ power_zone_percentages: editedPowerPct });
      onUserUpdate(updated);
      setEditMode(false);
      setFeedback({ type: "success", message: "Power zones saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save zones";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }
  
  function resetPowerZones() {
    setEditedPowerPct({ ...DEFAULT_POWER_ZONES });
  }
  
  function updatePowerPct(zone: string, field: "min" | "max", value: string) {
    const numVal = parseInt(value) || 0;
    setEditedPowerPct(prev => ({
      ...prev,
      [zone]: field === "min" ? [numVal, prev[zone][1]] : [prev[zone][0], value === "" ? null : numVal],
    }));
  }

  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Power Zones
        </CardTitle>
        <CardAction>
          {editMode ? (
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={cancelEdit} disabled={saving}>Cancel</Button>
              <Button size="sm" onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
            </div>
          ) : (
            <button onClick={startEdit} className="text-primary hover:text-primary/80 text-sm font-medium">Edit</button>
          )}
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="bg-muted/30 rounded-lg overflow-hidden border border-border">
          <div className="grid grid-cols-12 gap-4 px-4 py-3 bg-muted text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            <div className="col-span-1">Zone</div>
            <div className="col-span-3">Name</div>
            <div className="col-span-3">% FTP</div>
            <div className="col-span-3">Watts</div>
            <div className="col-span-2">Color</div>
          </div>
          {displayZones.map((z) => {
            const zoneKey = z.zone.toString();
            const color = POWER_ZONE_COLORS[zoneKey];
            return (
              <div key={z.zone} className="grid grid-cols-12 gap-4 px-4 py-3 border-t border-border items-center hover:bg-muted/50 transition">
                <div className="col-span-1">
                  <span className="inline-flex items-center justify-center w-8 h-8 rounded-full text-white font-bold text-sm" style={{ backgroundColor: color }}>{z.zone}</span>
                </div>
                <div className="col-span-3"><span className="text-sm text-foreground">{z.name}</span></div>
                <div className="col-span-3">
                  {editMode ? (
                    <div className="flex items-center gap-2">
                      <Input type="number" value={editedPowerPct[zoneKey][0]} onChange={(e) => updatePowerPct(zoneKey, "min", e.target.value)} className="w-16 h-9 text-sm text-right bg-muted" />
                      <span className="text-muted-foreground">-</span>
                      <Input type="number" value={editedPowerPct[zoneKey][1] ?? ""} onChange={(e) => updatePowerPct(zoneKey, "max", e.target.value)} placeholder="∞" className="w-16 h-9 text-sm text-right bg-muted" />
                      <span className="text-xs text-muted-foreground">%</span>
                    </div>
                  ) : (
                    <span className="text-sm text-foreground">{z.minPct}-{z.maxPct ?? "∞"}%</span>
                  )}
                </div>
                <div className="col-span-3"><span className="text-sm text-muted-foreground">{hasFtp ? `${z.minValue}-${z.maxValue ?? "∞"} W` : "— W"}</span></div>
                <div className="col-span-2"><div className="w-6 h-6 rounded border border-border" style={{ backgroundColor: color }} /></div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <p>Power zones use Coggan's 7-zone model. Customize names and ranges as needed.</p>
          {editMode && <button onClick={resetPowerZones} className="text-primary hover:text-primary/80 font-medium">Reset to defaults</button>}
        </div>
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}



function HrZonesCard({ 
  user: _user, 
  onUserUpdate, 
  hrZones,
  hrPercentages,
  hasLthr,
  lthr,
}: { 
  user: User; 
  onUserUpdate: (user: User) => void;
  hrZones: ReturnType<typeof computeHrZones>;
  hrPercentages: ZonePercentages;
  hasLthr: boolean;
  lthr: number | null;
}) {
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [editedHrPct, setEditedHrPct] = useState<ZonePercentages>(hrPercentages);
  
  const displayZones = editMode ? computeHrZones(lthr ?? 0, editedHrPct) : hrZones;
  
  function startEdit() {
    setEditedHrPct({ ...hrPercentages });
    setEditMode(true);
    setFeedback(null);
  }
  
  function cancelEdit() {
    setEditMode(false);
    setFeedback(null);
  }
  
  async function handleSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ hr_zone_percentages: editedHrPct });
      onUserUpdate(updated);
      setEditMode(false);
      setFeedback({ type: "success", message: "Heart rate zones saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save zones";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }
  
  function resetHrZones() {
    setEditedHrPct({ ...DEFAULT_HR_ZONES });
  }
  
  function updateHrPct(zone: string, field: "min" | "max", value: string) {
    const numVal = parseInt(value) || 0;
    setEditedHrPct(prev => ({
      ...prev,
      [zone]: field === "min" ? [numVal, prev[zone][1]] : [prev[zone][0], value === "" ? null : numVal],
    }));
  }

  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-pink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
          </svg>
          Heart Rate Zones
        </CardTitle>
        <CardAction>
          {editMode ? (
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={cancelEdit} disabled={saving}>Cancel</Button>
              <Button size="sm" onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
            </div>
          ) : (
            <button onClick={startEdit} className="text-primary hover:text-primary/80 text-sm font-medium">Edit</button>
          )}
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="bg-muted/30 rounded-lg overflow-hidden border border-border">
          <div className="grid grid-cols-12 gap-4 px-4 py-3 bg-muted text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            <div className="col-span-1">Zone</div>
            <div className="col-span-3">Name</div>
            <div className="col-span-3">% LTHR</div>
            <div className="col-span-3">BPM</div>
            <div className="col-span-2">Color</div>
          </div>
          {displayZones.map((z) => {
            const zoneKey = z.zone.toString();
            const color = HR_ZONE_COLORS[zoneKey];
            return (
              <div key={z.zone} className="grid grid-cols-12 gap-4 px-4 py-3 border-t border-border items-center hover:bg-muted/50 transition">
                <div className="col-span-1">
                  <span className="inline-flex items-center justify-center w-8 h-8 rounded-full text-white font-bold text-sm" style={{ backgroundColor: color }}>{z.zone}</span>
                </div>
                <div className="col-span-3"><span className="text-sm text-foreground">{z.name}</span></div>
                <div className="col-span-3">
                  {editMode ? (
                    <div className="flex items-center gap-2">
                      <Input type="number" value={editedHrPct[zoneKey][0]} onChange={(e) => updateHrPct(zoneKey, "min", e.target.value)} className="w-16 h-9 text-sm text-right bg-muted" />
                      <span className="text-muted-foreground">-</span>
                      <Input type="number" value={editedHrPct[zoneKey][1] ?? ""} onChange={(e) => updateHrPct(zoneKey, "max", e.target.value)} placeholder="∞" className="w-16 h-9 text-sm text-right bg-muted" />
                      <span className="text-xs text-muted-foreground">%</span>
                    </div>
                  ) : (
                    <span className="text-sm text-foreground">{z.minPct}-{z.maxPct ?? "∞"}%</span>
                  )}
                </div>
                <div className="col-span-3"><span className="text-sm text-foreground">{hasLthr ? `${z.minValue}-${z.maxValue ?? "∞"} bpm` : "— bpm"}</span></div>
                <div className="col-span-2"><div className="w-6 h-6 rounded border border-border" style={{ backgroundColor: color }} /></div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <p>Heart rate zones use the Friel method. Adjust percentages to match your training methodology.</p>
          {editMode && <button onClick={resetHrZones} className="text-primary hover:text-primary/80 font-medium">Reset to defaults</button>}
        </div>
        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}
