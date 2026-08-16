import { useState } from "react";
import type { User } from "@/api";
import { updatePreferences, ApiError } from "@/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { FeedbackAlert } from "./FeedbackAlert";

const MAP_TILE_STYLES = [
  { value: "osm" as const, label: "OpenStreetMap", preview: "/map-previews/osm.png" },
  { value: "positron" as const, label: "Positron", preview: "/map-previews/positron.png" },
  { value: "dark_matter" as const, label: "Dark Matter", preview: "/map-previews/dark_matter.png" },
  { value: "voyager" as const, label: "Voyager", preview: "/map-previews/voyager.png" },
];

interface MapSettingsProps {
  user: User;
  onUserUpdate: (user: User) => void;
}

export function MapSettings({ user, onUserUpdate }: MapSettingsProps) {
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [routeLineWidth, setRouteLineWidth] = useState(() => {
    const stored = localStorage.getItem("route_line_width");
    return stored ? parseFloat(stored) : 2;
  });

  async function handleStyleChange(style: typeof user.map_tile_style) {
    if (style === user.map_tile_style) return;
    
    setSaving(true);
    setFeedback(null);
    try {
      const updated = await updatePreferences({ map_tile_style: style });
      onUserUpdate(updated);
      setFeedback({ type: "success", message: "Map style updated" });
      setTimeout(() => setFeedback(null), 3000);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to update map style";
      setFeedback({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  function handleRouteLineWidthChange(width: number) {
    setRouteLineWidth(width);
    localStorage.setItem("route_line_width", width.toString());
  }


  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-title">
          <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Map Settings
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Map Style */}
        <div>
          <h3 className="font-medium text-foreground mb-3">Map Style</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Choose how maps appear throughout the app
          </p>

          <div className="grid grid-cols-2 gap-3 max-w-2xl">
            {MAP_TILE_STYLES.map(({ value, label, preview }) => {
              const isSelected = user.map_tile_style === value;
              return (
                <button
                  key={value}
                  onClick={() => handleStyleChange(value)}
                  disabled={saving}
                  className={cn(
                    "relative rounded-lg overflow-hidden border-2 transition-all text-left aspect-[16/7]",
                    isSelected
                      ? "border-primary"
                      : "border-border hover:border-muted-foreground/50",
                    saving && "opacity-50 cursor-not-allowed"
                  )}
                >
                  <img
                    src={preview}
                    alt={`${label} map style preview`}
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-3 py-2">
                    <span className="text-sm font-medium text-white">{label}</span>
                  </div>
                  {isSelected && (
                    <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-primary flex items-center justify-center shadow-md">
                      <svg className="w-3 h-3 text-primary-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>


        {/* Route Line Thickness */}
        <div className="pt-6 border-t border-border">
          <h3 className="font-medium text-foreground mb-3">Route Line Thickness</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Adjust the width of route lines on maps
          </p>
          
          <div className="max-w-md">
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="1"
                max="5"
                step="0.5"
                value={routeLineWidth}
                onChange={(e) => handleRouteLineWidthChange(parseFloat(e.target.value))}
                disabled={saving}
                className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <div className="w-20 text-right">
                <span className="text-lg font-semibold text-foreground">{routeLineWidth.toFixed(1)}</span>
                <span className="text-xs text-muted-foreground ml-1">px</span>
              </div>
            </div>
            <div className="flex justify-between mt-2 text-xs text-muted-foreground">
              <span>Thin (1px)</span>
              <span>Thick (5px)</span>
            </div>
          </div>
        </div>

        <FeedbackAlert feedback={feedback} />
      </CardContent>
    </Card>
  );
}
