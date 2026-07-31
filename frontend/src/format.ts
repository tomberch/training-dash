export function formatDistance(m: number): string {
  return `${(m / 1000).toFixed(1)} km`;
}

export function formatTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${sec}s`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-CH", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}