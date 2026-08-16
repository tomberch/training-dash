interface ZoneChartProps {
  title: string;
  zoneTimes: Record<string, number>;
  zoneColors: Record<string, string>;
}

export function ZoneChart({ title, zoneTimes, zoneColors }: ZoneChartProps) {
  // Convert zone times to array and calculate percentages
  const zones = Object.entries(zoneTimes)
    .map(([zone, seconds]) => ({
      zone,
      seconds,
      label: `Z${zone}`,
    }))
    .sort((a, b) => parseInt(a.zone) - parseInt(b.zone));

  const totalSeconds = zones.reduce((sum, z) => sum + z.seconds, 0);
  
  if (totalSeconds === 0) return null;

  const formatZoneTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <h3 className="text-sm font-semibold text-foreground mb-4">{title}</h3>
      <div className="space-y-2">
        {zones.map(({ zone, seconds, label }) => {
          const percentage = (seconds / totalSeconds) * 100;
          const color = zoneColors[zone] || "#6b7280";

          return (
            <div key={zone} className="flex items-center gap-3">
              <div className="w-32 text-xs font-medium text-muted-foreground shrink-0">
                {label}: {percentage.toFixed(0)}%{" "}
                <span className="text-muted-foreground/70">
                  ({formatZoneTime(seconds)})
                </span>
              </div>
              <div className="flex-1 h-5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.max(percentage, 1)}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-border flex justify-between text-caption">
        <span>Total</span>
        <span className="tabular-nums">{formatZoneTime(totalSeconds)}</span>
      </div>
    </div>
  );
}
