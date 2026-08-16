/**
 * PROTOTYPE: Segment System UI Surfaces
 * 
 * This is throwaway code to explore different layouts for segment-related UI.
 * Switch between surfaces using the ?surface=suggestion|detail|list|create query param.
 * Switch between variants using &variant=1|2|3
 * 
 * Surfaces to prototype:
 * 1. Segment suggestion card (activity detail inline)
 * 2. Segment detail page (map, profile, efforts)
 * 3. Suggestions page (pending suggestions list)
 * 4. Manual segment creation (start/end selection)
 */

import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// =============================================================================
// MOCK DATA
// =============================================================================

const MOCK_SEGMENT = {
  id: "seg-123",
  name: "Col de la Madone",
  type: "climb" as const,
  status: "approved" as const,
  climb_category: "2" as const,
  distance_m: 12400,
  elevation_gain_m: 927,
  avg_grade_pct: 7.5,
  max_grade_pct: 12.1,
  effort_count: 1847,
  athlete_count: 423,
  direction_bearing: 45,
};


const MOCK_SUGGESTED_SEGMENT = {
  id: "seg-456",
  name: null,
  type: "climb" as const,
  status: "suggested" as const,
  climb_category: "4" as const,
  distance_m: 2100,
  elevation_gain_m: 156,
  avg_grade_pct: 7.4,
  max_grade_pct: 11.2,
  effort_count: 0,
  athlete_count: 0,
  repetition_count: 5,
  first_seen_at: "2024-06-15",
  last_seen_at: "2024-08-10",
};

const MOCK_GRADIENT_SEGMENTS = [
  { start_m: 0, end_m: 50, avg_grade_pct: 3.2 },
  { start_m: 50, end_m: 100, avg_grade_pct: 5.1 },
  { start_m: 100, end_m: 150, avg_grade_pct: 6.8 },
  { start_m: 150, end_m: 200, avg_grade_pct: 8.2 },
  { start_m: 200, end_m: 250, avg_grade_pct: 9.5 },
  { start_m: 250, end_m: 300, avg_grade_pct: 7.1 },
  { start_m: 300, end_m: 350, avg_grade_pct: 6.3 },
  { start_m: 350, end_m: 400, avg_grade_pct: 8.9 },
  { start_m: 400, end_m: 450, avg_grade_pct: 11.2 },
  { start_m: 450, end_m: 500, avg_grade_pct: 10.1 },
  { start_m: 500, end_m: 550, avg_grade_pct: 8.4 },
  { start_m: 550, end_m: 600, avg_grade_pct: 7.2 },
];

const MOCK_EFFORTS = [
  { id: "e1", elapsed_time_s: 2847, avg_power_w: 285, avg_hr_bpm: 168, date: "2024-08-10", is_pr: true },
  { id: "e2", elapsed_time_s: 2912, avg_power_w: 278, avg_hr_bpm: 165, date: "2024-07-22", is_pr: false },
  { id: "e3", elapsed_time_s: 2956, avg_power_w: 271, avg_hr_bpm: 162, date: "2024-06-15", is_pr: false },
  { id: "e4", elapsed_time_s: 3021, avg_power_w: 265, avg_hr_bpm: 159, date: "2024-05-28", is_pr: false },
  { id: "e5", elapsed_time_s: 3089, avg_power_w: 258, avg_hr_bpm: 161, date: "2024-04-12", is_pr: false },
];

const MOCK_SUGGESTIONS = [
  { ...MOCK_SUGGESTED_SEGMENT, id: "sug-1", repetition_count: 5, climb_category: "4" as const },
  { ...MOCK_SUGGESTED_SEGMENT, id: "sug-2", repetition_count: 3, climb_category: "uncategorized" as const,
    distance_m: 850, elevation_gain_m: 42, avg_grade_pct: 4.9 },
  { ...MOCK_SUGGESTED_SEGMENT, id: "sug-3", repetition_count: 7, climb_category: "3" as const,
    distance_m: 5200, elevation_gain_m: 385, avg_grade_pct: 7.4 },
];


// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatTimeDelta(currentSeconds: number, prSeconds: number): string {
  const delta = currentSeconds - prSeconds;
  const sign = delta >= 0 ? "+" : "-";
  const absDelta = Math.abs(delta);
  const m = Math.floor(absDelta / 60);
  const s = absDelta % 60;
  return `${sign}${m}:${s.toString().padStart(2, "0")}`;
}

function ClimbCategoryBadge({ category }: { category: string | null }) {
  if (!category) return null;
  const colors: Record<string, string> = {
    HC: "bg-purple-600 text-white",
    "1": "bg-red-600 text-white",
    "2": "bg-orange-500 text-white",
    "3": "bg-yellow-500 text-black",
    "4": "bg-green-500 text-white",
    uncategorized: "bg-muted text-muted-foreground",
  };
  const label = category === "uncategorized" ? "UC" : `Cat ${category}`;
  return (
    <span className={cn("px-2 py-0.5 rounded text-xs font-bold", colors[category] || colors.uncategorized)}>
      {label}
    </span>
  );
}

function SegmentTypeBadge({ type }: { type: "climb" | "sprint" | "arbitrary" }) {
  const config = {
    climb: { icon: "▲", color: "text-orange-500" },
    sprint: { icon: "⚡", color: "text-blue-500" },
    arbitrary: { icon: "◆", color: "text-muted-foreground" },
  };
  const { icon, color } = config[type];
  return <span className={cn("text-lg", color)}>{icon}</span>;
}


function GradientProfile({ segments, height = 60 }: { segments: typeof MOCK_GRADIENT_SEGMENTS; height?: number }) {
  const maxGrade = Math.max(...segments.map(s => s.avg_grade_pct));
  const getColor = (grade: number) => {
    if (grade >= 10) return "#dc2626"; // red
    if (grade >= 8) return "#f97316";  // orange
    if (grade >= 6) return "#eab308";  // yellow
    if (grade >= 4) return "#22c55e";  // green
    return "#6b7280";                   // gray
  };
  
  return (
    <div className="flex items-end gap-px" style={{ height }}>
      {segments.map((seg, i) => (
        <div
          key={i}
          className="flex-1 rounded-t-sm transition-all hover:opacity-80"
          style={{
            height: `${(seg.avg_grade_pct / maxGrade) * 100}%`,
            backgroundColor: getColor(seg.avg_grade_pct),
            minHeight: 4,
          }}
          title={`${seg.avg_grade_pct.toFixed(1)}%`}
        />
      ))}
    </div>
  );
}

function MiniMap({ className }: { className?: string }) {
  // Placeholder for map - in real implementation would use Leaflet/MapLibre
  return (
    <div className={cn("bg-muted rounded-lg flex items-center justify-center text-muted-foreground", className)}>
      <svg className="w-8 h-8 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} 
          d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    </div>
  );
}

function StatItem({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div>
      <div className="text-caption">{label}</div>
      <div className="font-semibold">
        {value}{unit && <span className="text-muted-foreground text-sm ml-0.5">{unit}</span>}
      </div>
    </div>
  );
}


// =============================================================================
// SURFACE 1: SEGMENT SUGGESTION CARD (Activity Detail Inline)
// =============================================================================

function SuggestionCardVariant1() {
  // Compact inline card
  return (
    <Card className="border-dashed border-primary/50 bg-primary/5">
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          <div className="w-20 h-20 flex-shrink-0">
            <MiniMap className="w-full h-full" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium text-primary">Suggested Segment</span>
              <ClimbCategoryBadge category={MOCK_SUGGESTED_SEGMENT.climb_category} />
            </div>
            <div className="text-sm text-muted-foreground mb-2">
              {(MOCK_SUGGESTED_SEGMENT.distance_m / 1000).toFixed(1)} km · {MOCK_SUGGESTED_SEGMENT.elevation_gain_m}m ↑ · {MOCK_SUGGESTED_SEGMENT.avg_grade_pct}% avg
            </div>
            <div className="text-caption mb-3">
              You've ridden this {MOCK_SUGGESTED_SEGMENT.repetition_count} times
            </div>
            <div className="flex gap-2">
              <Button size="sm">Save Segment</Button>
              <Button size="sm" variant="ghost">Dismiss</Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SuggestionCardVariant2() {
  // Expanded card with gradient profile
  return (
    <Card className="border-primary/30 bg-gradient-to-r from-primary/5 to-transparent">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <SegmentTypeBadge type="climb" />
          <span className="text-sm font-medium">Climb Detected</span>
          <ClimbCategoryBadge category={MOCK_SUGGESTED_SEGMENT.climb_category} />
          <span className="text-caption ml-auto">{MOCK_SUGGESTED_SEGMENT.repetition_count}× ridden</span>
        </div>
        
        <div className="grid grid-cols-2 gap-4 mb-4">
          <MiniMap className="h-24" />
          <div className="space-y-2">
            <GradientProfile segments={MOCK_GRADIENT_SEGMENTS} height={40} />
            <div className="grid grid-cols-3 gap-2 text-sm">
              <StatItem label="Distance" value={(MOCK_SUGGESTED_SEGMENT.distance_m / 1000).toFixed(1)} unit="km" />
              <StatItem label="Elevation" value={MOCK_SUGGESTED_SEGMENT.elevation_gain_m} unit="m" />
              <StatItem label="Avg Grade" value={MOCK_SUGGESTED_SEGMENT.avg_grade_pct} unit="%" />
            </div>
          </div>
        </div>
        
        <div className="flex gap-2">
          <Button size="sm" className="flex-1">Save as Segment</Button>
          <Button size="sm" variant="outline">Later</Button>
          <Button size="sm" variant="ghost">Dismiss</Button>
        </div>
      </CardContent>
    </Card>
  );
}


function SuggestionCardVariant3() {
  // Minimal badge-style with expand
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="border border-dashed border-primary/40 rounded-lg overflow-hidden">
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full p-3 flex items-center gap-3 hover:bg-primary/5 transition-colors"
      >
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <SegmentTypeBadge type="climb" />
        </div>
        <div className="flex-1 text-left">
          <div className="text-sm font-medium">Segment opportunity detected</div>
          <div className="text-caption">
            {(MOCK_SUGGESTED_SEGMENT.distance_m / 1000).toFixed(1)} km climb · {MOCK_SUGGESTED_SEGMENT.repetition_count}× ridden
          </div>
        </div>
        <ClimbCategoryBadge category={MOCK_SUGGESTED_SEGMENT.climb_category} />
        <svg className={cn("w-5 h-5 transition-transform", expanded && "rotate-180")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {expanded && (
        <div className="p-4 pt-0 border-t border-border">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <MiniMap className="h-32" />
            <div>
              <GradientProfile segments={MOCK_GRADIENT_SEGMENTS} height={48} />
              <div className="grid grid-cols-2 gap-2 mt-3 text-sm">
                <StatItem label="Distance" value={(MOCK_SUGGESTED_SEGMENT.distance_m / 1000).toFixed(1)} unit="km" />
                <StatItem label="Elevation" value={MOCK_SUGGESTED_SEGMENT.elevation_gain_m} unit="m" />
                <StatItem label="Avg Grade" value={MOCK_SUGGESTED_SEGMENT.avg_grade_pct} unit="%" />
                <StatItem label="Max Grade" value={MOCK_SUGGESTED_SEGMENT.max_grade_pct} unit="%" />
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" className="flex-1">Save Segment</Button>
            <Button size="sm" variant="ghost">Not Interested</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function SuggestionCard({ variant }: { variant: number }) {
  return (
    <div className="p-6 max-w-2xl mx-auto space-y-4">
      <h2 className="text-lg font-semibold mb-4">Suggestion Card (Activity Detail)</h2>
      <p className="text-muted-foreground text-sm mb-6">
        This card appears on the activity detail page when we detect a climb the user has ridden multiple times.
      </p>
      {variant === 1 && <SuggestionCardVariant1 />}
      {variant === 2 && <SuggestionCardVariant2 />}
      {variant === 3 && <SuggestionCardVariant3 />}
    </div>
  );
}


// =============================================================================
// SURFACE 2: SEGMENT DETAIL PAGE
// =============================================================================

function SegmentDetailVariant1() {
  // Full-width hero style (like event detail variant 1)
  const prEffort = MOCK_EFFORTS.find(e => e.is_pr)!;
  
  return (
    <div className="-m-6">
      {/* Header with map background */}
      <div className="relative h-48 bg-muted">
        <MiniMap className="w-full h-full rounded-none" />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/50 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-6">
          <div className="flex items-center gap-3 mb-2">
            <SegmentTypeBadge type={MOCK_SEGMENT.type} />
            <ClimbCategoryBadge category={MOCK_SEGMENT.climb_category} />
          </div>
          <h1 className="text-2xl font-bold">{MOCK_SEGMENT.name}</h1>
        </div>
      </div>
      
      {/* Stats bar */}
      <div className="border-b border-border px-6 py-4">
        <div className="grid grid-cols-5 gap-4 text-center">
          <StatItem label="Distance" value={(MOCK_SEGMENT.distance_m / 1000).toFixed(1)} unit="km" />
          <StatItem label="Elevation" value={MOCK_SEGMENT.elevation_gain_m} unit="m" />
          <StatItem label="Avg Grade" value={MOCK_SEGMENT.avg_grade_pct} unit="%" />
          <StatItem label="Max Grade" value={MOCK_SEGMENT.max_grade_pct} unit="%" />
          <StatItem label="Efforts" value={MOCK_SEGMENT.effort_count} />
        </div>
      </div>
      
      {/* Gradient profile */}
      <div className="px-6 py-4 border-b border-border">
        <h3 className="text-sm font-medium mb-2">Gradient Profile</h3>
        <GradientProfile segments={MOCK_GRADIENT_SEGMENTS} height={80} />
        <div className="flex justify-between text-caption mt-1">
          <span>0 km</span>
          <span>{(MOCK_SEGMENT.distance_m / 1000).toFixed(1)} km</span>
        </div>
      </div>


      {/* PR highlight */}
      <div className="px-6 py-4 border-b border-border bg-amber-500/5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-amber-500/20 flex items-center justify-center">
            <span className="text-2xl">🏆</span>
          </div>
          <div className="flex-1">
            <div className="text-caption">Your PR</div>
            <div className="text-2xl font-bold text-amber-600">{formatTime(prEffort.elapsed_time_s)}</div>
          </div>
          <div className="text-right">
            <div className="text-caption">Power</div>
            <div className="font-semibold">{prEffort.avg_power_w}w</div>
          </div>
          <div className="text-right">
            <div className="text-caption">Heart Rate</div>
            <div className="font-semibold">{prEffort.avg_hr_bpm} bpm</div>
          </div>
        </div>
      </div>
      
      {/* Efforts list */}
      <div className="px-6 py-4">
        <h3 className="text-sm font-medium mb-3">Your Efforts</h3>
        <div className="space-y-2">
          {MOCK_EFFORTS.map((effort) => (
            <div key={effort.id} className={cn(
              "flex items-center gap-4 p-3 rounded-lg",
              effort.is_pr ? "bg-amber-500/10 border border-amber-500/20" : "bg-muted/50"
            )}>
              {effort.is_pr && <span className="text-amber-500">★</span>}
              <div className="font-mono font-semibold">{formatTime(effort.elapsed_time_s)}</div>
              <div className="text-muted-foreground">
                {!effort.is_pr && formatTimeDelta(effort.elapsed_time_s, prEffort.elapsed_time_s)}
              </div>
              <div className="flex-1" />
              <div className="text-sm text-muted-foreground">{effort.avg_power_w}w</div>
              <div className="text-sm text-muted-foreground">{effort.avg_hr_bpm} bpm</div>
              <div className="text-caption">{new Date(effort.date).toLocaleDateString()}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


function SegmentDetailVariant2() {
  // Two-column layout: map/profile left, stats/efforts right
  const prEffort = MOCK_EFFORTS.find(e => e.is_pr)!;
  
  return (
    <div className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <SegmentTypeBadge type={MOCK_SEGMENT.type} />
        <h1 className="text-xl font-bold">{MOCK_SEGMENT.name}</h1>
        <ClimbCategoryBadge category={MOCK_SEGMENT.climb_category} />
      </div>
      
      <div className="grid grid-cols-3 gap-6">
        {/* Left: Map and profile */}
        <div className="col-span-2 space-y-4">
          <Card>
            <CardContent className="p-0">
              <MiniMap className="h-64 rounded-t-lg rounded-b-none" />
              <div className="p-4">
                <h3 className="text-sm font-medium mb-2">Gradient Profile</h3>
                <GradientProfile segments={MOCK_GRADIENT_SEGMENTS} height={60} />
              </div>
            </CardContent>
          </Card>
          
          {/* Efforts table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Your Efforts</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b">
                    <th className="pb-2">Time</th>
                    <th className="pb-2">+/-</th>
                    <th className="pb-2">Power</th>
                    <th className="pb-2">HR</th>
                    <th className="pb-2">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {MOCK_EFFORTS.map((effort) => (
                    <tr key={effort.id} className={cn("border-b last:border-0", effort.is_pr && "bg-amber-500/5")}>
                      <td className="py-2 font-mono">
                        {effort.is_pr && <span className="text-amber-500 mr-1">★</span>}
                        {formatTime(effort.elapsed_time_s)}
                      </td>
                      <td className="py-2 text-muted-foreground">
                        {effort.is_pr ? "PR" : formatTimeDelta(effort.elapsed_time_s, prEffort.elapsed_time_s)}
                      </td>
                      <td className="py-2">{effort.avg_power_w}w</td>
                      <td className="py-2">{effort.avg_hr_bpm}</td>
                      <td className="py-2 text-muted-foreground">{new Date(effort.date).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>


        {/* Right: Stats sidebar */}
        <div className="space-y-4">
          {/* PR card */}
          <Card className="border-amber-500/30 bg-amber-500/5">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <span className="text-amber-500">★</span> Your PR
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-600 mb-2">
                {formatTime(prEffort.elapsed_time_s)}
              </div>
              <div className="text-sm text-muted-foreground">
                {prEffort.avg_power_w}w · {prEffort.avg_hr_bpm} bpm
              </div>
              <div className="text-caption mt-1">
                {new Date(prEffort.date).toLocaleDateString()}
              </div>
            </CardContent>
          </Card>
          
          {/* Segment stats */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Segment Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Distance</span>
                <span className="font-medium">{(MOCK_SEGMENT.distance_m / 1000).toFixed(1)} km</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Elevation</span>
                <span className="font-medium">{MOCK_SEGMENT.elevation_gain_m} m</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Avg Grade</span>
                <span className="font-medium">{MOCK_SEGMENT.avg_grade_pct}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Max Grade</span>
                <span className="font-medium">{MOCK_SEGMENT.max_grade_pct}%</span>
              </div>
              <div className="border-t pt-3 mt-3">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Efforts</span>
                  <span className="font-medium">{MOCK_SEGMENT.effort_count}</span>
                </div>
                <div className="flex justify-between mt-2">
                  <span className="text-muted-foreground">Athletes</span>
                  <span className="font-medium">{MOCK_SEGMENT.athlete_count}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}


function SegmentDetailVariant3() {
  // Compact single-column with expandable sections
  const prEffort = MOCK_EFFORTS.find(e => e.is_pr)!;
  const [showAllEfforts, setShowAllEfforts] = useState(false);
  
  return (
    <div className="p-6 max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <SegmentTypeBadge type={MOCK_SEGMENT.type} />
            <ClimbCategoryBadge category={MOCK_SEGMENT.climb_category} />
          </div>
          <h1 className="text-xl font-bold">{MOCK_SEGMENT.name}</h1>
          <div className="text-sm text-muted-foreground mt-1">
            {(MOCK_SEGMENT.distance_m / 1000).toFixed(1)} km · {MOCK_SEGMENT.elevation_gain_m}m ↑ · {MOCK_SEGMENT.avg_grade_pct}% avg
          </div>
        </div>
        <div className="text-right">
          <div className="text-caption">Your PR</div>
          <div className="text-2xl font-bold text-amber-600">{formatTime(prEffort.elapsed_time_s)}</div>
        </div>
      </div>
      
      {/* Map + Profile */}
      <Card>
        <CardContent className="p-0">
          <div className="grid grid-cols-2">
            <MiniMap className="h-40 rounded-l-lg rounded-r-none" />
            <div className="p-4 flex flex-col justify-between">
              <GradientProfile segments={MOCK_GRADIENT_SEGMENTS} height={60} />
              <div className="grid grid-cols-2 gap-2 text-sm mt-2">
                <StatItem label="Max Grade" value={MOCK_SEGMENT.max_grade_pct} unit="%" />
                <StatItem label="Efforts" value={MOCK_SEGMENT.effort_count} />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Efforts */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Your Efforts ({MOCK_EFFORTS.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(showAllEfforts ? MOCK_EFFORTS : MOCK_EFFORTS.slice(0, 3)).map((effort) => (
            <div key={effort.id} className={cn(
              "flex items-center gap-3 p-2 rounded",
              effort.is_pr && "bg-amber-500/10"
            )}>
              {effort.is_pr ? (
                <span className="text-amber-500 w-5">★</span>
              ) : (
                <span className="w-5" />
              )}
              <span className="font-mono font-medium w-20">{formatTime(effort.elapsed_time_s)}</span>
              <span className="text-muted-foreground text-sm w-16">
                {effort.is_pr ? "" : formatTimeDelta(effort.elapsed_time_s, prEffort.elapsed_time_s)}
              </span>
              <span className="text-sm">{effort.avg_power_w}w</span>
              <span className="flex-1" />
              <span className="text-caption">{new Date(effort.date).toLocaleDateString()}</span>
            </div>
          ))}
          {MOCK_EFFORTS.length > 3 && (
            <Button variant="ghost" size="sm" className="w-full" onClick={() => setShowAllEfforts(!showAllEfforts)}>
              {showAllEfforts ? "Show less" : `Show all ${MOCK_EFFORTS.length} efforts`}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SegmentDetail({ variant }: { variant: number }) {
  return (
    <>
      {variant === 1 && <SegmentDetailVariant1 />}
      {variant === 2 && <SegmentDetailVariant2 />}
      {variant === 3 && <SegmentDetailVariant3 />}
    </>
  );
}


// =============================================================================
// SURFACE 3: SUGGESTIONS PAGE (List of pending suggestions)
// =============================================================================

function SuggestionsListVariant1() {
  // Card grid
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Suggested Segments</h1>
          <p className="text-muted-foreground text-sm">Climbs detected from your rides</p>
        </div>
        <Button variant="outline" size="sm">Dismiss All</Button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {MOCK_SUGGESTIONS.map((suggestion) => (
          <Card key={suggestion.id} className="overflow-hidden">
            <div className="grid grid-cols-3">
              <MiniMap className="h-full rounded-none" />
              <div className="col-span-2 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <ClimbCategoryBadge category={suggestion.climb_category} />
                  <span className="text-caption">{suggestion.repetition_count}× ridden</span>
                </div>
                <div className="text-sm mb-1">
                  {(suggestion.distance_m / 1000).toFixed(1)} km · {suggestion.elevation_gain_m}m ↑
                </div>
                <div className="text-caption mb-3">
                  {suggestion.avg_grade_pct}% avg grade
                </div>
                <div className="flex gap-2">
                  <Button size="sm">Save</Button>
                  <Button size="sm" variant="ghost">Dismiss</Button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function SuggestionsListVariant2() {
  // Compact list
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Segment Suggestions</h1>
          <p className="text-muted-foreground text-sm">{MOCK_SUGGESTIONS.length} climbs detected</p>
        </div>
      </div>
      
      <div className="space-y-3">
        {MOCK_SUGGESTIONS.map((suggestion) => (
          <div key={suggestion.id} className="flex items-center gap-4 p-4 bg-card border rounded-lg">
            <MiniMap className="w-16 h-16 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <ClimbCategoryBadge category={suggestion.climb_category} />
                <span className="text-sm font-medium">
                  {(suggestion.distance_m / 1000).toFixed(1)} km · {suggestion.elevation_gain_m}m
                </span>
              </div>
              <div className="text-caption mt-1">
                {suggestion.avg_grade_pct}% avg · {suggestion.repetition_count} rides
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm">Save</Button>
              <Button size="sm" variant="ghost" className="text-muted-foreground">×</Button>
            </div>
          </div>
        ))}
      </div>
      
      {MOCK_SUGGESTIONS.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <p>No segment suggestions</p>
          <p className="text-sm mt-1">Keep riding — we'll detect climbs you do repeatedly</p>
        </div>
      )}
    </div>
  );
}


function SuggestionsListVariant3() {
  // Table-style with inline actions
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Suggested Segments</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">Save All</Button>
          <Button variant="ghost" size="sm">Clear All</Button>
        </div>
      </div>
      
      <Card>
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-muted-foreground border-b">
                <th className="p-4">Preview</th>
                <th className="p-4">Category</th>
                <th className="p-4">Distance</th>
                <th className="p-4">Elevation</th>
                <th className="p-4">Grade</th>
                <th className="p-4">Rides</th>
                <th className="p-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_SUGGESTIONS.map((suggestion) => (
                <tr key={suggestion.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="p-4">
                    <MiniMap className="w-12 h-12" />
                  </td>
                  <td className="p-4">
                    <ClimbCategoryBadge category={suggestion.climb_category} />
                  </td>
                  <td className="p-4">{(suggestion.distance_m / 1000).toFixed(1)} km</td>
                  <td className="p-4">{suggestion.elevation_gain_m} m</td>
                  <td className="p-4">{suggestion.avg_grade_pct}%</td>
                  <td className="p-4">{suggestion.repetition_count}×</td>
                  <td className="p-4">
                    <div className="flex gap-1">
                      <Button size="sm" variant="outline">Save</Button>
                      <Button size="sm" variant="ghost">×</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function SuggestionsList({ variant }: { variant: number }) {
  return (
    <>
      {variant === 1 && <SuggestionsListVariant1 />}
      {variant === 2 && <SuggestionsListVariant2 />}
      {variant === 3 && <SuggestionsListVariant3 />}
    </>
  );
}


// =============================================================================
// SURFACE 4: MANUAL SEGMENT CREATION
// =============================================================================

function SegmentCreationVariant1() {
  // Slider-based selection (Strava-style)
  const [startPct, setStartPct] = useState(20);
  const [endPct, setEndPct] = useState(60);
  const [name, setName] = useState("");
  
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-xl font-bold mb-2">Create Segment</h1>
      <p className="text-muted-foreground text-sm mb-6">
        Select the start and end points on your activity
      </p>
      
      {/* Map with selection */}
      <Card className="mb-6">
        <CardContent className="p-0">
          <div className="relative">
            <MiniMap className="h-64 rounded-t-lg rounded-b-none" />
            <div className="absolute bottom-4 left-4 right-4 bg-background/90 backdrop-blur rounded-lg p-3">
              <div className="text-sm font-medium mb-2">Selection: {startPct}% → {endPct}%</div>
              <div className="relative h-2 bg-muted rounded-full">
                <div 
                  className="absolute h-full bg-primary rounded-full"
                  style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
                />
              </div>
              <div className="flex justify-between mt-2">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={startPct}
                  onChange={(e) => setStartPct(Math.min(Number(e.target.value), endPct - 5))}
                  className="w-1/2"
                />
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={endPct}
                  onChange={(e) => setEndPct(Math.max(Number(e.target.value), startPct + 5))}
                  className="w-1/2"
                />
              </div>
            </div>
          </div>
          
          {/* Preview stats */}
          <div className="p-4 border-t grid grid-cols-4 gap-4 text-center">
            <StatItem label="Distance" value="2.4" unit="km" />
            <StatItem label="Elevation" value="186" unit="m" />
            <StatItem label="Avg Grade" value="7.8" unit="%" />
            <StatItem label="Max Grade" value="12.1" unit="%" />
          </div>
        </CardContent>
      </Card>
      
      {/* Name input */}
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Segment Name</Label>
          <Input 
            id="name" 
            value={name} 
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Hawk Hill Climb"
            className="mt-1"
          />
        </div>
        
        <div className="flex gap-3">
          <Button className="flex-1">Create Segment</Button>
          <Button variant="outline">Cancel</Button>
        </div>
      </div>
    </div>
  );
}


function SegmentCreationVariant2() {
  // Split view: map left, controls right
  const [name, setName] = useState("");
  
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-6">Create Segment</h1>
      
      <div className="grid grid-cols-2 gap-6">
        {/* Map */}
        <Card>
          <CardContent className="p-0">
            <MiniMap className="h-96 rounded-lg" />
          </CardContent>
        </Card>
        
        {/* Controls */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Selection</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-sm text-muted-foreground">Start Point</Label>
                <div className="flex items-center gap-2 mt-1">
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span>km 4.2 · 523m elevation</span>
                  <Button size="sm" variant="ghost" className="ml-auto">Adjust</Button>
                </div>
              </div>
              <div>
                <Label className="text-sm text-muted-foreground">End Point</Label>
                <div className="flex items-center gap-2 mt-1">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <span>km 6.6 · 709m elevation</span>
                  <Button size="sm" variant="ghost" className="ml-auto">Adjust</Button>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Preview</CardTitle>
            </CardHeader>
            <CardContent>
              <GradientProfile segments={MOCK_GRADIENT_SEGMENTS} height={48} />
              <div className="grid grid-cols-2 gap-4 mt-4">
                <StatItem label="Distance" value="2.4" unit="km" />
                <StatItem label="Elevation" value="186" unit="m" />
                <StatItem label="Avg Grade" value="7.8" unit="%" />
                <StatItem label="Max Grade" value="12.1" unit="%" />
              </div>
            </CardContent>
          </Card>
          
          <div className="space-y-3">
            <div>
              <Label htmlFor="name2">Segment Name</Label>
              <Input 
                id="name2" 
                value={name} 
                onChange={(e) => setName(e.target.value)}
                placeholder="Name your segment"
                className="mt-1"
              />
            </div>
            <Button className="w-full">Create Segment</Button>
          </div>
        </div>
      </div>
    </div>
  );
}


function SegmentCreationVariant3() {
  // Step-by-step wizard
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  
  return (
    <div className="p-6 max-w-2xl mx-auto">
      {/* Progress */}
      <div className="flex items-center gap-2 mb-8">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium",
              step >= s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}>
              {s}
            </div>
            {s < 3 && <div className={cn("w-12 h-0.5", step > s ? "bg-primary" : "bg-muted")} />}
          </div>
        ))}
      </div>
      
      {step === 1 && (
        <div>
          <h2 className="text-lg font-semibold mb-2">Select Start Point</h2>
          <p className="text-muted-foreground text-sm mb-4">Click on the map to set where your segment begins</p>
          <Card>
            <CardContent className="p-0">
              <MiniMap className="h-64 rounded-lg cursor-crosshair" />
            </CardContent>
          </Card>
          <div className="flex justify-end mt-4">
            <Button onClick={() => setStep(2)}>Set Start Point</Button>
          </div>
        </div>
      )}
      
      {step === 2 && (
        <div>
          <h2 className="text-lg font-semibold mb-2">Select End Point</h2>
          <p className="text-muted-foreground text-sm mb-4">Click on the map to set where your segment ends</p>
          <Card>
            <CardContent className="p-0">
              <MiniMap className="h-64 rounded-lg cursor-crosshair" />
            </CardContent>
          </Card>
          <div className="flex justify-between mt-4">
            <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
            <Button onClick={() => setStep(3)}>Set End Point</Button>
          </div>
        </div>
      )}
      
      {step === 3 && (
        <div>
          <h2 className="text-lg font-semibold mb-2">Name Your Segment</h2>
          <p className="text-muted-foreground text-sm mb-4">Review and save your segment</p>
          
          <Card className="mb-4">
            <CardContent className="p-4">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <MiniMap className="h-32" />
                <div>
                  <GradientProfile segments={MOCK_GRADIENT_SEGMENTS} height={40} />
                  <div className="grid grid-cols-2 gap-2 mt-2 text-sm">
                    <StatItem label="Distance" value="2.4" unit="km" />
                    <StatItem label="Elevation" value="186" unit="m" />
                  </div>
                </div>
              </div>
              <div>
                <Label htmlFor="name3">Segment Name</Label>
                <Input 
                  id="name3" 
                  value={name} 
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Local Hill Sprint"
                  className="mt-1"
                />
              </div>
            </CardContent>
          </Card>
          
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
            <Button>Create Segment</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function SegmentCreation({ variant }: { variant: number }) {
  return (
    <>
      {variant === 1 && <SegmentCreationVariant1 />}
      {variant === 2 && <SegmentCreationVariant2 />}
      {variant === 3 && <SegmentCreationVariant3 />}
    </>
  );
}


// =============================================================================
// NAVIGATION & EXPORT
// =============================================================================

type Surface = "suggestion" | "detail" | "list" | "create";

function SurfaceSwitcher({ current, onChange }: { current: Surface; onChange: (s: Surface) => void }) {
  const surfaces: { key: Surface; label: string }[] = [
    { key: "suggestion", label: "Suggestion Card" },
    { key: "detail", label: "Segment Detail" },
    { key: "list", label: "Suggestions List" },
    { key: "create", label: "Create Segment" },
  ];
  
  return (
    <div className="fixed top-20 left-1/2 -translate-x-1/2 bg-card border border-border rounded-lg shadow-lg p-1 flex gap-1 z-50">
      {surfaces.map(s => (
        <button
          key={s.key}
          onClick={() => onChange(s.key)}
          className={cn(
            "px-3 py-1.5 rounded text-sm font-medium transition-colors",
            current === s.key ? "bg-primary text-primary-foreground" : "hover:bg-muted"
          )}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}

function VariantSwitcher({ current, onChange }: { current: number; onChange: (v: number) => void }) {
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-card border border-border rounded-lg shadow-lg p-2 flex gap-2 z-50">
      {[1, 2, 3].map(v => (
        <button
          key={v}
          onClick={() => onChange(v)}
          className={cn(
            "px-3 py-1.5 rounded text-sm font-medium transition-colors",
            current === v ? "bg-primary text-primary-foreground" : "hover:bg-muted"
          )}
        >
          Variant {v}
        </button>
      ))}
    </div>
  );
}

export function PrototypeSegments() {
  const [searchParams, setSearchParams] = useSearchParams();
  const surface = (searchParams.get("surface") || "suggestion") as Surface;
  const variant = parseInt(searchParams.get("variant") || "1", 10);

  const setSurface = (s: Surface) => {
    setSearchParams({ surface: s, variant: variant.toString() });
  };
  
  const setVariant = (v: number) => {
    setSearchParams({ surface, variant: v.toString() });
  };

  return (
    <div className="pt-16">
      <SurfaceSwitcher current={surface} onChange={setSurface} />
      
      {surface === "suggestion" && <SuggestionCard variant={variant} />}
      {surface === "detail" && <SegmentDetail variant={variant} />}
      {surface === "list" && <SuggestionsList variant={variant} />}
      {surface === "create" && <SegmentCreation variant={variant} />}
      
      <VariantSwitcher current={variant} onChange={setVariant} />
    </div>
  );
}
