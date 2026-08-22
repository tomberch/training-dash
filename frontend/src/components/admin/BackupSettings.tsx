/**
 * Backup Settings panel for admin.
 *
 * Backup is enabled when BACKUP_HOST_PATH is set in the environment.
 * If not configured, shows a message explaining how to enable it.
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

  // Form state for schedule/retention
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

  // Not configured - show setup instructions
  if (!config?.configured) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backup Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-border bg-muted/50 p-4">
            <h3 className="font-medium text-foreground mb-2">Backup Not Configured</h3>
            <p className="text-body-secondary mb-3">
              To enable backups, set the <code className="px-1.5 py-0.5 bg-muted rounded text-sm font-mono">BACKUP_HOST_PATH</code> environment
              variable to the directory where you want backups stored.
            </p>
            <div className="bg-card rounded border border-border p-3 font-mono text-sm">
              <p className="text-muted-foreground"># In your .env file or docker-compose.yml:</p>
              <p className="text-foreground">BACKUP_HOST_PATH=/path/to/your/backups</p>
            </div>
            <p className="text-caption mt-3">
              After setting this variable, restart the containers for changes to take effect.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Path configured but invalid - show error
  if (!config.path_valid) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backup Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <h3 className="font-medium text-destructive mb-2">Backup Path Invalid</h3>
            <p className="text-body-secondary mb-3">
              The backup path is configured but cannot be used:
            </p>
            <div className="bg-card rounded border border-border p-3 mb-3">
              <p className="text-sm">
                <span className="text-muted-foreground">Path:</span>{" "}
                <code className="font-mono">{config.host_path}</code>
              </p>
              <p className="text-sm text-destructive mt-1">
                <span className="text-muted-foreground">Error:</span>{" "}
                {config.path_error}
              </p>
            </div>
            <p className="text-caption">
              Make sure the path exists on the host and is properly mounted into the container.
              Check that the directory has write permissions.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const hasChanges =
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
          {/* Backup location (read-only) */}
          <div className="space-y-1.5">
            <Label>Backup Location</Label>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2 bg-muted rounded border border-border text-sm font-mono">
                {config.host_path}
              </code>
              <span className="px-2 py-1 text-xs font-medium rounded-full bg-success/20 text-success">
                Active
              </span>
            </div>
            <p className="text-caption">
              Configured via BACKUP_HOST_PATH environment variable.
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
              {saving ? "Saving..." : "Save Settings"}
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
            disabled={triggering || status?.is_running}
          >
            {triggering || status?.is_running ? "Running..." : "Backup Now"}
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
