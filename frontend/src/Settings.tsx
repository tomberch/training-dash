import { useState, useEffect } from "react";
import {
  updatePreferences,
  fetchMyXertCredentials,
  saveMyXertCredentials,
  deleteMyXertCredentials,
  fetchMyGarminCredentials,
  saveMyGarminCredentials,
  completeGarminMfa,
  deleteMyGarminCredentials,
  fetchThresholds,
  createThreshold,
  fetchZones,
  updateZones,
  ApiError,
} from "./api";
import type { 
  User, 
  XertCredentialsStatus, 
  GarminCredentialsStatus,
  ThresholdEntry,
  PowerZone,
  HrZone,
} from "./api";

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

function EyeSlashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
    </svg>
  );
}

function PasswordInput({
  value,
  onChange,
  placeholder,
  "data-testid": dataTestId,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  "data-testid"?: string;
}) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="relative">
      <input
        type={showPassword ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid={dataTestId}
        className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
      />
      <button
        type="button"
        onClick={() => setShowPassword(!showPassword)}
        className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        tabIndex={-1}
      >
        {showPassword ? (
          <EyeSlashIcon className="w-5 h-5" />
        ) : (
          <EyeIcon className="w-5 h-5" />
        )}
      </button>
    </div>
  );
}

interface SettingsProps {
  user: User;
  onBack: () => void;
  onUserUpdate: (user: User) => void;
}

export function Settings({ user, onBack, onUserUpdate }: SettingsProps) {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <button
          onClick={onBack}
          className="mb-6 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          &larr; Back
        </button>
        
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Settings</h1>
        
        <div className="space-y-6">
          <PreferencesSection user={user} onUserUpdate={onUserUpdate} />
          <ThresholdsSection />
          <ZonesSection />
          <IntegrationsSection />
        </div>
      </div>
    </div>
  );
}

function PreferencesSection({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  async function handleToggle() {
    const newSystem = user.unit_system === "metric" ? "imperial" : "metric";
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ unit_system: newSystem });
      onUserUpdate(updated);
      setFeedback({ type: "success", message: "Preferences saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save preferences";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Preferences</h2>
      
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-white">Unit System</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Display distances, elevations, and speeds in {user.unit_system === "metric" ? "kilometers and meters" : "miles and feet"}
          </p>
        </div>
        
        <button
          onClick={handleToggle}
          disabled={saving}
          data-testid="unit-toggle"
          className={`relative inline-flex h-9 w-36 items-center rounded-lg transition-colors ${
            saving ? "opacity-50 cursor-not-allowed" : ""
          } ${
            user.unit_system === "metric"
              ? "bg-indigo-100 dark:bg-indigo-900/30"
              : "bg-green-100 dark:bg-green-900/30"
          }`}
        >
          <span
            className={`absolute inset-y-1 w-[calc(50%-4px)] rounded-md bg-white dark:bg-gray-700 shadow transition-transform ${
              user.unit_system === "imperial" ? "translate-x-[calc(100%+4px)] ml-1" : "ml-1"
            }`}
          />
          <span
            className={`relative z-10 flex-1 text-center text-sm font-medium transition-colors ${
              user.unit_system === "metric"
                ? "text-indigo-700 dark:text-indigo-300"
                : "text-gray-500 dark:text-gray-400"
            }`}
          >
            Metric
          </span>
          <span
            className={`relative z-10 flex-1 text-center text-sm font-medium transition-colors ${
              user.unit_system === "imperial"
                ? "text-green-700 dark:text-green-300"
                : "text-gray-500 dark:text-gray-400"
            }`}
          >
            Imperial
          </span>
        </button>
      </div>
      
      {feedback && (
        <div
          className={`mt-4 p-3 rounded-lg text-sm ${
            feedback.type === "success"
              ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
              : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
          }`}
        >
          {feedback.message}
        </div>
      )}
    </section>
  );
}

function ThresholdsSection() {
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    effective_date: new Date().toISOString().split("T")[0],
    ftp_watts: "",
    lthr_bpm: "",
    hrmax_bpm: "",
  });
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetchThresholds()
      .then(setThresholds)
      .catch(() => setThresholds([]))
      .finally(() => setLoading(false));
  }, []);

  const currentThreshold = thresholds.length > 0 ? thresholds[0] : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFeedback(null);
    try {
      const newThreshold = await createThreshold({
        effective_date: formData.effective_date,
        ftp_watts: parseInt(formData.ftp_watts),
        lthr_bpm: parseInt(formData.lthr_bpm),
        hrmax_bpm: parseInt(formData.hrmax_bpm),
      });
      setThresholds([newThreshold, ...thresholds]);
      setShowForm(false);
      setFormData({
        effective_date: new Date().toISOString().split("T")[0],
        ftp_watts: "",
        lthr_bpm: "",
        hrmax_bpm: "",
      });
      setFeedback({ type: "success", message: "Threshold saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save threshold";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse">
          <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    );
  }

  return (
    <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Thresholds</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 rounded-lg transition-colors"
        >
          {showForm ? "Cancel" : "+ Add"}
        </button>
      </div>

      {/* Current values */}
      {currentThreshold && (
        <div className="grid grid-cols-3 gap-4 mb-4 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">FTP</div>
            <div className="text-xl font-bold text-gray-900 dark:text-white">{currentThreshold.ftp_watts}W</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">LTHR</div>
            <div className="text-xl font-bold text-gray-900 dark:text-white">{currentThreshold.lthr_bpm} bpm</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">HRmax</div>
            <div className="text-xl font-bold text-gray-900 dark:text-white">{currentThreshold.max_hr_bpm} bpm</div>
          </div>
        </div>
      )}

      {/* Add form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="mb-4 p-4 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Effective Date</label>
              <input
                type="date"
                value={formData.effective_date}
                onChange={(e) => setFormData({ ...formData, effective_date: e.target.value })}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">FTP (watts)</label>
              <input
                type="number"
                value={formData.ftp_watts}
                onChange={(e) => setFormData({ ...formData, ftp_watts: e.target.value })}
                placeholder="e.g. 250"
                min="50"
                max="600"
                required
                className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">LTHR (bpm)</label>
              <input
                type="number"
                value={formData.lthr_bpm}
                onChange={(e) => setFormData({ ...formData, lthr_bpm: e.target.value })}
                placeholder="e.g. 165"
                min="80"
                max="220"
                required
                className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">HRmax (bpm)</label>
              <input
                type="number"
                value={formData.hrmax_bpm}
                onChange={(e) => setFormData({ ...formData, hrmax_bpm: e.target.value })}
                placeholder="e.g. 185"
                min="100"
                max="250"
                required
                className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="w-full px-3 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Threshold"}
          </button>
        </form>
      )}

      {/* History table */}
      {thresholds.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide border-b border-gray-200 dark:border-gray-700">
                <th className="pb-2">Date</th>
                <th className="pb-2 text-right">FTP</th>
                <th className="pb-2 text-right">LTHR</th>
                <th className="pb-2 text-right">HRmax</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {thresholds.map((t, i) => (
                <tr key={i} className={i === 0 ? "text-gray-900 dark:text-white font-medium" : "text-gray-600 dark:text-gray-400"}>
                  <td className="py-2">{new Date(t.effective_date).toLocaleDateString()}</td>
                  <td className="py-2 text-right">{t.ftp_watts}W</td>
                  <td className="py-2 text-right">{t.lthr_bpm} bpm</td>
                  <td className="py-2 text-right">{t.max_hr_bpm} bpm</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {thresholds.length === 0 && !showForm && (
        <p className="text-sm text-gray-500 dark:text-gray-400">No thresholds configured. Add your first threshold to enable zone calculations.</p>
      )}

      {feedback && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${
          feedback.type === "success"
            ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
            : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
        }`}>
          {feedback.message}
        </div>
      )}
    </section>
  );
}

function ZonesSection() {
  const [powerZones, setPowerZones] = useState<PowerZone[]>([]);
  const [hrZones, setHrZones] = useState<HrZone[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedPowerZones, setEditedPowerZones] = useState<PowerZone[]>([]);
  const [editedHrZones, setEditedHrZones] = useState<HrZone[]>([]);

  useEffect(() => {
    fetchZones()
      .then(({ power_zones, hr_zones }) => {
        setPowerZones(power_zones);
        setHrZones(hr_zones);
      })
      .catch(() => {
        setPowerZones([]);
        setHrZones([]);
      })
      .finally(() => setLoading(false));
  }, []);

  function startEdit() {
    setEditedPowerZones([...powerZones]);
    setEditedHrZones([...hrZones]);
    setEditMode(true);
  }

  function cancelEdit() {
    setEditMode(false);
    setFeedback(null);
  }

  async function handleSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const result = await updateZones({
        power_zones: editedPowerZones.map(z => ({
          zone_number: z.zone_number,
          min_value: z.min_watts,
          max_value: z.max_watts ?? undefined,
        })),
        hr_zones: editedHrZones.map(z => ({
          zone_number: z.zone_number,
          min_value: z.min_bpm,
          max_value: z.max_bpm ?? undefined,
        })),
      });
      setPowerZones(result.power_zones);
      setHrZones(result.hr_zones);
      setEditMode(false);
      setFeedback({ type: "success", message: "Zones saved" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to save zones";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    if (!confirm("Reset all zones to defaults based on current thresholds?")) return;
    setSaving(true);
    setFeedback(null);
    try {
      const result = await updateZones({ reset_to_defaults: true });
      setPowerZones(result.power_zones);
      setHrZones(result.hr_zones);
      setEditMode(false);
      setFeedback({ type: "success", message: "Zones reset to defaults" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to reset zones";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  function updatePowerZone(index: number, field: "min_watts" | "max_watts", value: string) {
    const updated = [...editedPowerZones];
    const numVal = parseInt(value) || 0;
    if (field === "max_watts") {
      updated[index] = { ...updated[index], [field]: value === "" ? null : numVal };
    } else {
      updated[index] = { ...updated[index], [field]: numVal };
    }
    setEditedPowerZones(updated);
  }

  function updateHrZone(index: number, field: "min_bpm" | "max_bpm", value: string) {
    const updated = [...editedHrZones];
    const numVal = parseInt(value) || 0;
    if (field === "max_bpm") {
      updated[index] = { ...updated[index], [field]: value === "" ? null : numVal };
    } else {
      updated[index] = { ...updated[index], [field]: numVal };
    }
    setEditedHrZones(updated);
  }

  if (loading) {
    return (
      <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse">
          <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    );
  }

  const displayPowerZones = editMode ? editedPowerZones : powerZones;
  const displayHrZones = editMode ? editedHrZones : hrZones;

  return (
    <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Training Zones</h2>
        <div className="flex gap-2">
          {editMode ? (
            <>
              <button
                onClick={cancelEdit}
                disabled={saving}
                className="px-3 py-1.5 text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save"}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleReset}
                disabled={saving || powerZones.length === 0}
                className="px-3 py-1.5 text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
              >
                Reset
              </button>
              <button
                onClick={startEdit}
                disabled={powerZones.length === 0}
                className="px-3 py-1.5 text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 rounded-lg transition-colors disabled:opacity-50"
              >
                Edit
              </button>
            </>
          )}
        </div>
      </div>

      {powerZones.length === 0 && hrZones.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Add thresholds first to generate training zones.</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Power Zones */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Power Zones</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide border-b border-gray-200 dark:border-gray-700">
                  <th className="pb-2 w-8">Zone</th>
                  <th className="pb-2">Name</th>
                  <th className="pb-2 text-right">Min</th>
                  <th className="pb-2 text-right">Max</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {displayPowerZones.map((z, i) => (
                  <tr key={z.zone_number}>
                    <td className="py-2 font-medium text-gray-900 dark:text-white">Z{z.zone_number}</td>
                    <td className="py-2 text-gray-600 dark:text-gray-400">{z.name}</td>
                    <td className="py-2 text-right">
                      {editMode ? (
                        <input
                          type="number"
                          value={z.min_watts}
                          onChange={(e) => updatePowerZone(i, "min_watts", e.target.value)}
                          className="w-16 px-1 py-0.5 text-right text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                      ) : (
                        <span className="text-gray-900 dark:text-white">{z.min_watts}W</span>
                      )}
                    </td>
                    <td className="py-2 text-right">
                      {editMode ? (
                        <input
                          type="number"
                          value={z.max_watts ?? ""}
                          onChange={(e) => updatePowerZone(i, "max_watts", e.target.value)}
                          placeholder="∞"
                          className="w-16 px-1 py-0.5 text-right text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                      ) : (
                        <span className="text-gray-900 dark:text-white">{z.max_watts ? `${z.max_watts}W` : "∞"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* HR Zones */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Heart Rate Zones</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide border-b border-gray-200 dark:border-gray-700">
                  <th className="pb-2 w-8">Zone</th>
                  <th className="pb-2">Name</th>
                  <th className="pb-2 text-right">Min</th>
                  <th className="pb-2 text-right">Max</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {displayHrZones.map((z, i) => (
                  <tr key={z.zone_number}>
                    <td className="py-2 font-medium text-gray-900 dark:text-white">Z{z.zone_number}</td>
                    <td className="py-2 text-gray-600 dark:text-gray-400">{z.name}</td>
                    <td className="py-2 text-right">
                      {editMode ? (
                        <input
                          type="number"
                          value={z.min_bpm}
                          onChange={(e) => updateHrZone(i, "min_bpm", e.target.value)}
                          className="w-16 px-1 py-0.5 text-right text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                      ) : (
                        <span className="text-gray-900 dark:text-white">{z.min_bpm} bpm</span>
                      )}
                    </td>
                    <td className="py-2 text-right">
                      {editMode ? (
                        <input
                          type="number"
                          value={z.max_bpm ?? ""}
                          onChange={(e) => updateHrZone(i, "max_bpm", e.target.value)}
                          placeholder="∞"
                          className="w-16 px-1 py-0.5 text-right text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                      ) : (
                        <span className="text-gray-900 dark:text-white">{z.max_bpm ? `${z.max_bpm} bpm` : "∞"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {feedback && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${
          feedback.type === "success"
            ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
            : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
        }`}>
          {feedback.message}
        </div>
      )}
    </section>
  );
}

function IntegrationsSection() {
  return (
    <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Integrations</h2>
      
      <div className="space-y-4">
        <XertIntegration />
        <GarminIntegration />
      </div>
    </section>
  );
}

function XertIntegration() {
  const [xertStatus, setXertStatus] = useState<XertCredentialsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [syncSince, setSyncSince] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 90);
    return date.toISOString().split("T")[0];
  });
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetchMyXertCredentials()
      .then((status) => {
        setXertStatus(status);
        if (status.configured && status.xert_email) {
          setEmail(status.xert_email);
        }
        if (status.sync_since) {
          setSyncSince(status.sync_since);
        }
      })
      .catch(() => {
        setXertStatus({ configured: false, xert_email: null, sync_since: null });
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleConnect() {
    if (!email || !password) return;
    setSaving(true);
    setFeedback(null);
    try {
      await saveMyXertCredentials(email, password, syncSince);
      setXertStatus({ configured: true, xert_email: email, sync_since: syncSince });
      setPassword("");
      setFeedback({ type: "success", message: "Xert connected successfully" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setFeedback({ type: "error", message: "Invalid Xert credentials — check your email and password" });
      } else {
        setFeedback({ type: "error", message: "Failed to connect to Xert" });
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnect() {
    setSaving(true);
    setFeedback(null);
    try {
      await deleteMyXertCredentials();
      setXertStatus({ configured: false, xert_email: null, sync_since: null });
      setEmail("");
      setPassword("");
      setFeedback({ type: "success", message: "Xert disconnected" });
      setTimeout(() => setFeedback(null), 3000);
    } catch {
      setFeedback({ type: "error", message: "Failed to disconnect Xert" });
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-2"></div>
          <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">Xert</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {xertStatus?.configured
              ? `Connected as ${xertStatus.xert_email}`
              : "Not connected"}
          </p>
        </div>
        <span
          data-testid="xert-status"
          className={`px-2 py-1 text-xs font-medium rounded-full ${
            xertStatus?.configured
              ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
              : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400"
          }`}
        >
          {xertStatus?.configured ? "Connected" : "Not configured"}
        </span>
      </div>
      
      <div className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Xert Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
            data-testid="xert-email"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Xert Password
          </label>
          <PasswordInput
            value={password}
            onChange={setPassword}
            placeholder={xertStatus?.configured ? "Enter new password to update" : "Enter password"}
            data-testid="xert-password"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Sync activities since
          </label>
          <input
            type="date"
            value={syncSince}
            onChange={(e) => setSyncSince(e.target.value)}
            data-testid="xert-sync-since"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Activities from this date onwards will be imported
          </p>
        </div>
        
        <div className="flex gap-3 pt-2">
          <button
            onClick={handleConnect}
            disabled={saving || !email || !password}
            data-testid="xert-connect"
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              saving || !email || !password
                ? "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed"
                : "bg-indigo-600 text-white hover:bg-indigo-700"
            }`}
          >
            {saving ? "Connecting..." : xertStatus?.configured ? "Update" : "Connect"}
          </button>
          
          {xertStatus?.configured && (
            <button
              onClick={handleDisconnect}
              disabled={saving}
              data-testid="xert-disconnect"
              className="px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors disabled:opacity-50"
            >
              Disconnect
            </button>
          )}
        </div>
      </div>
      
      {feedback && (
        <div
          data-testid="xert-feedback"
          className={`mt-4 p-3 rounded-lg text-sm ${
            feedback.type === "success"
              ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
              : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
          }`}
        >
          {feedback.message}
        </div>
      )}
    </div>
  );
}



function GarminIntegration() {
  const [garminStatus, setGarminStatus] = useState<GarminCredentialsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [syncSince, setSyncSince] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 90);
    return date.toISOString().split("T")[0];
  });
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetchMyGarminCredentials()
      .then((status) => {
        setGarminStatus(status);
        if (status.configured && status.garmin_email) {
          setEmail(status.garmin_email);
        }
        if (status.sync_since) {
          setSyncSince(status.sync_since);
        }
      })
      .catch(() => {
        setGarminStatus({ configured: false, garmin_email: null, sync_since: null });
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleConnect() {
    if (!email || !password) return;
    setSaving(true);
    setFeedback(null);
    try {
      const response = await saveMyGarminCredentials(email, password, syncSince);
      if (response.mfa_required) {
        setMfaRequired(true);
        setFeedback({ type: "success", message: "MFA required — enter the code from your authenticator app or email" });
      } else {
        setGarminStatus({ configured: true, garmin_email: email, sync_since: syncSince });
        setPassword("");
        setMfaRequired(false);
        setMfaCode("");
        setFeedback({ type: "success", message: "Garmin connected successfully" });
        setTimeout(() => setFeedback(null), 3000);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setFeedback({ type: "error", message: "Invalid Garmin credentials — check your email and password" });
      } else {
        setFeedback({ type: "error", message: "Failed to connect to Garmin" });
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleMfaSubmit() {
    if (!mfaCode) return;
    setSaving(true);
    setFeedback(null);
    try {
      await completeGarminMfa(mfaCode);
      setGarminStatus({ configured: true, garmin_email: email, sync_since: syncSince });
      setPassword("");
      setMfaRequired(false);
      setMfaCode("");
      setFeedback({ type: "success", message: "Garmin connected successfully" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setFeedback({ type: "error", message: "Invalid MFA code — please try again" });
      } else {
        setFeedback({ type: "error", message: "Failed to complete MFA" });
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnect() {
    setSaving(true);
    setFeedback(null);
    try {
      await deleteMyGarminCredentials();
      setGarminStatus({ configured: false, garmin_email: null, sync_since: null });
      setEmail("");
      setPassword("");
      setMfaRequired(false);
      setMfaCode("");
      setFeedback({ type: "success", message: "Garmin disconnected" });
      setTimeout(() => setFeedback(null), 3000);
    } catch {
      setFeedback({ type: "error", message: "Failed to disconnect Garmin" });
    } finally {
      setSaving(false);
    }
  }

  function handleCancelMfa() {
    setMfaRequired(false);
    setMfaCode("");
    setPassword("");
    setFeedback(null);
  }

  if (loading) {
    return (
      <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-2"></div>
          <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-gray-900 dark:text-white">Garmin</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {garminStatus?.configured
              ? `Connected as ${garminStatus.garmin_email}`
              : "Not connected"}
          </p>
        </div>
        <span
          data-testid="garmin-status"
          className={`px-2 py-1 text-xs font-medium rounded-full ${
            garminStatus?.configured
              ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
              : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400"
          }`}
        >
          {garminStatus?.configured ? "Connected" : "Not configured"}
        </span>
      </div>
      
      {mfaRequired ? (
        <MfaForm
          mfaCode={mfaCode}
          setMfaCode={setMfaCode}
          saving={saving}
          onSubmit={handleMfaSubmit}
          onCancel={handleCancelMfa}
        />
      ) : (
        <GarminCredentialsForm
          email={email}
          setEmail={setEmail}
          password={password}
          setPassword={setPassword}
          syncSince={syncSince}
          setSyncSince={setSyncSince}
          saving={saving}
          configured={garminStatus?.configured ?? false}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
        />
      )}
      
      {feedback && (
        <div
          data-testid="garmin-feedback"
          className={`mt-4 p-3 rounded-lg text-sm ${
            feedback.type === "success"
              ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
              : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
          }`}
        >
          {feedback.message}
        </div>
      )}
    </div>
  );
}

function MfaForm({
  mfaCode,
  setMfaCode,
  saving,
  onSubmit,
  onCancel,
}: {
  mfaCode: string;
  setMfaCode: (v: string) => void;
  saving: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          MFA Code
        </label>
        <input
          type="text"
          value={mfaCode}
          onChange={(e) => setMfaCode(e.target.value)}
          placeholder="Enter 6-digit code"
          data-testid="garmin-mfa-code"
          autoComplete="one-time-code"
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Enter the code from your Garmin authenticator app or email
        </p>
      </div>
      
      <div className="flex gap-3 pt-2">
        <button
          onClick={onSubmit}
          disabled={saving || !mfaCode}
          data-testid="garmin-mfa-submit"
          className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
            saving || !mfaCode
              ? "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed"
              : "bg-indigo-600 text-white hover:bg-indigo-700"
          }`}
        >
          {saving ? "Verifying..." : "Verify"}
        </button>
        
        <button
          onClick={onCancel}
          disabled={saving}
          className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function GarminCredentialsForm({
  email,
  setEmail,
  password,
  setPassword,
  syncSince,
  setSyncSince,
  saving,
  configured,
  onConnect,
  onDisconnect,
}: {
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  syncSince: string;
  setSyncSince: (v: string) => void;
  saving: boolean;
  configured: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
}) {
  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Garmin Email
        </label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="your@email.com"
          data-testid="garmin-email"
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        />
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Garmin Password
        </label>
        <PasswordInput
          value={password}
          onChange={setPassword}
          placeholder={configured ? "Enter new password to update" : "Enter password"}
          data-testid="garmin-password"
        />
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Sync activities since
        </label>
        <input
          type="date"
          value={syncSince}
          onChange={(e) => setSyncSince(e.target.value)}
          data-testid="garmin-sync-since"
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Activities from this date onwards will be imported
        </p>
      </div>
      
      <div className="flex gap-3 pt-2">
        <button
          onClick={onConnect}
          disabled={saving || !email || !password}
          data-testid="garmin-connect"
          className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
            saving || !email || !password
              ? "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed"
              : "bg-indigo-600 text-white hover:bg-indigo-700"
          }`}
        >
          {saving ? "Connecting..." : configured ? "Update" : "Connect"}
        </button>
        
        {configured && (
          <button
            onClick={onDisconnect}
            disabled={saving}
            data-testid="garmin-disconnect"
            className="px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors disabled:opacity-50"
          >
            Disconnect
          </button>
        )}
      </div>
    </div>
  );
}
