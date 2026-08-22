/**
 * Backup Settings panel for admin.
 * Allows configuring backup schedule, retention, and triggering manual backups.
 */
import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  fetchBackupConfig,
  updateBackupConfig,
  fetchBackupHistory,
  fetchBackupStatus,
  triggerBackup,
  type BackupConfig,
  type BackupHistoryEntry,
  type BackupStatus,
} from "@/api";

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "-";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleString();
}

interface BackupSettingsProps {
  onError?: (error: Error) => void;
}

export function BackupSettings({ onError }: BackupSettingsProps) {
  const [config, setConfig] = useState<BackupConfig | null>(null);
  const [history, setHistory] = useState<BackupHistoryEntry[]>([]);
  const [status, setStatus] = useState<BackupStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);

  // Form state
  const [enabled, setEnabled] = useState(false);
  const [repositoryPath, setRepositoryPath] = useState("/data/backups");
  const [scheduleHour, setScheduleHour] = useState<number | null>(null);
  const [keepDaily, setKeepDaily] = useState(7);
  const [keepWeekly, setKeepWeekly] = useState(4);
  const [keepMonthly, setKeepMonthly] = useState(3);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [configData, historyData, statusData] = await Promise.all([
        fetchBackupConfig(),
        fetchBackupHistory(10),
        fetchBackupStatus(),
      ]);

      setConfig(configData);
      setHistory(historyData.entries);
      setStatus(statusData);

      // Initialize form with config values
      if (configData) {
        setEnabled(configData.enabled);
        setRepositoryPath(configData.repository_path);
        setScheduleHour(configData.schedule_hour);
        setKeepDaily(configData.retention_keep_daily);
        setKeepWeekly(configData.retention_keep_weekly);
        setKeepMonthly(configData.retention_keep_monthly);
      }
    } catch (e) {
      onError?.(e as Error);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateBackupConfig({
        enabled,
        repository_path: repositoryPath,
        schedule_hour: scheduleHour,
        retention_keep_daily: keepDaily,
        retention_keep_weekly: keepWeekly,
        retention_keep_monthly: keepMonthly,
      });
      setConfig(updated);
    } catch (e) {
      onError?.(e as Error);
    } finally {
      setSaving(false);
    }
  }

  async function handleTriggerBackup() {
    setTriggering(true);
    try {
      await triggerBackup();
      // Refresh status and history
      const [historyData, statusData] = await Promise.all([
        fetchBackupHistory(10),
        fetchBackupStatus(),
      ]);
      setHistory(historyData.entries);
      setStatus(statusData);
    } catch (e) {
      onError?.(e as Error);
    } finally {
      setTriggering(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backup Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  const hasChanges =
    config === null ||
    enabled !== config.enabled ||
    repositoryPath !== config.repository_path ||
    scheduleHour !== config.schedule_hour ||
    keepDaily !== config.retention_keep_daily ||
    keepWeekly !== config.retention_keep_weekly ||
    keepMonthly !== config.retention_keep_monthly;

  return (
    <div className="space-y-6">
      {/* Configuration Card */}
      <Card>
        <CardHeader>
          <CardTitle>Backup Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Enable toggle */}
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-base">Enable Backups</Label>
              <p className="text-body-secondary">
                Enable automated database and uploads backup using restic
              </p>
            </div>
            <button
              onClick={() => setEnabled(!enabled)}
              className={cn(
                "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
                enabled ? "bg-primary" : "bg-muted"
              )}
            >
              <span
                className={cn(
                  "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                  enabled ? "translate-x-6" : "translate-x-1"
                )}
              />
            </button>
          </div>

          {/* Repository path */}
          <div className="space-y-1.5">
            <Label>Repository Path</Label>
            <Input
              value={repositoryPath}
              onChange={(e) => setRepositoryPath(e.target.value)}
              placeholder="/data/backups"
            />
            <p className="text-caption">
              Path to the restic repository. Will be created on first backup.
            </p>
          </div>

          {/* Schedule */}
          <div className="space-y-1.5">
            <Label>Schedule (UTC hour)</Label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                min={0}
                max={23}
                value={scheduleHour ?? ""}
                onChange={(e) =>
                  setScheduleHour(e.target.value ? parseInt(e.target.value, 10) : null)
                }
                placeholder="e.g. 3"
                className="w-24"
              />
              <span className="text-body-secondary">
                {scheduleHour !== null
                  ? `Daily at ${scheduleHour.toString().padStart(2, "0")}:00 UTC`
                  : "Manual only (no schedule)"}
              </span>
            </div>
          </div>

          {/* Retention policy */}
          <div className="space-y-3">
            <Label className="text-base">Retention Policy</Label>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label className="text-sm">Keep Daily</Label>
                <Input
                  type="number"
                  min={1}
                  max={365}
                  value={keepDaily}
                  onChange={(e) => setKeepDaily(parseInt(e.target.value, 10) || 7)}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Keep Weekly</Label>
                <Input
                  type="number"
                  min={0}
                  max={52}
                  value={keepWeekly}
                  onChange={(e) => setKeepWeekly(parseInt(e.target.value, 10) || 0)}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Keep Monthly</Label>
                <Input
                  type="number"
                  min={0}
                  max={24}
                  value={keepMonthly}
                  onChange={(e) => setKeepMonthly(parseInt(e.target.value, 10) || 0)}
                />
              </div>
            </div>
          </div>

          {/* Save button */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving || !hasChanges}>
              {saving ? "Saving..." : "Save Configuration"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Status & Trigger Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Backup Status</CardTitle>
          <Button
            variant="outline"
            onClick={handleTriggerBackup}
            disabled={triggering || status?.is_running || !config?.enabled}
          >
            {triggering || status?.is_running ? "Running..." : "Trigger Backup Now"}
          </Button>
        </CardHeader>
        <CardContent>
          {status?.is_running ? (
            <div className="flex items-center gap-2 text-warning">
              <div className="h-2 w-2 rounded-full bg-warning animate-pulse" />
              <span>Backup in progress...</span>
            </div>
          ) : status?.latest_backup ? (
            <div className="space-y-1">
              <p className="text-body">
                Last backup:{" "}
                <span
                  className={cn(
                    "font-medium",
                    status.latest_backup.status === "completed"
                      ? "text-success"
                      : "text-destructive"
                  )}
                >
                  {status.latest_backup.status}
                </span>
              </p>
              <p className="text-body-secondary">
                {formatDate(status.latest_backup.completed_at)}
              </p>
              {status.latest_backup.snapshot_id && (
                <p className="text-caption font-mono">
                  Snapshot: {status.latest_backup.snapshot_id.slice(0, 12)}...
                </p>
              )}
            </div>
          ) : (
            <p className="text-body-secondary">No backups yet</p>
          )}
          {!config?.enabled && (
            <p className="text-caption text-warning mt-2">
              Enable backups above to trigger a backup.
            </p>
          )}
        </CardContent>
      </Card>

      {/* History Card */}
      <Card>
        <CardHeader>
          <CardTitle>Backup History</CardTitle>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <p className="text-body-secondary">No backup history yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 px-3 text-left text-section-heading">Started</th>
                    <th className="py-2 px-3 text-left text-section-heading">Status</th>
                    <th className="py-2 px-3 text-left text-section-heading">Trigger</th>
                    <th className="py-2 px-3 text-left text-section-heading">Duration</th>
                    <th className="py-2 px-3 text-left text-section-heading">Size Added</th>
                    <th className="py-2 px-3 text-left text-section-heading">Files</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {history.map((entry) => (
                    <tr key={entry.id} className="hover:bg-muted/50">
                      <td className="py-2 px-3 text-foreground">
                        {formatDate(entry.started_at)}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={cn(
                            "inline-flex px-2 py-0.5 text-xs font-medium rounded-full",
                            entry.status === "completed" &&
                              "bg-success/20 text-success",
                            entry.status === "running" &&
                              "bg-warning/20 text-warning",
                            entry.status === "failed" &&
                              "bg-destructive/20 text-destructive"
                          )}
                        >
                          {entry.status}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-muted-foreground">
                        {entry.trigger_type}
                      </td>
                      <td className="py-2 px-3 text-muted-foreground tabular-nums">
                        {formatDuration(entry.duration_seconds)}
                      </td>
                      <td className="py-2 px-3 text-muted-foreground tabular-nums">
                        {formatBytes(entry.bytes_added)}
                      </td>
                      <td className="py-2 px-3 text-muted-foreground tabular-nums">
                        {entry.files_new !== null || entry.files_changed !== null
                          ? `${entry.files_new ?? 0} new, ${entry.files_changed ?? 0} changed`
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
