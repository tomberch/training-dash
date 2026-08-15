/**
 * PROTOTYPE: Event Detail Page Layout Variations
 * 
 * This is throwaway code to explore different layouts for the Event detail page.
 * Switch between variations using the ?variant=1|2|3 query param.
 * 
 * Questions to answer:
 * 1. How prominent should the cover image be?
 * 2. How should aggregate stats be presented?
 * 3. How should the day-by-day timeline look?
 * 4. How does single-day vs multi-day feel?
 */

import { useSearchParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Mock data for prototype - toggle between multi-day and single-day
const MULTI_DAY_EVENT = {
  id: "123",
  title: "Alps Bikepacking 2024",
  description: `A 5-day adventure through the French Alps, crossing iconic cols and discovering hidden valleys. 

Started in Grenoble, climbed Col du Galibier on day 2, then traversed to Briançon. The highlight was definitely the descent from Col d'Izoard with stunning views of the Casse Déserte.`,
  event_type: "bikepacking" as const,
  start_date: "2024-07-15",
  end_date: "2024-07-19",
  cover_image_url: "https://images.unsplash.com/photo-1507035895480-2b3156c31fc8?w=1200",
};

const SINGLE_DAY_EVENT = {
  id: "456",
  title: "Bern Grand Prix 2024",
  description: `Local crit race around the old town. 40 laps, 52km total. Finished 12th out of 67 starters — happy with the result after a mechanical in lap 15 cost me the lead group.`,
  event_type: "race" as const,
  start_date: "2024-08-10",
  end_date: "2024-08-10",
  cover_image_url: "https://images.unsplash.com/photo-1517649763962-0c623066013b?w=1200",
};


const MULTI_DAY_STATS = {
  total_distance_km: 423,
  total_elevation_m: 12450,
  total_time_hours: 28.5,
  total_activities: 5,
  total_photos: 47,
};

const SINGLE_DAY_STATS = {
  total_distance_km: 52,
  total_elevation_m: 320,
  total_time_hours: 1.5,
  total_activities: 1,
  total_photos: 8,
};

const MULTI_DAY_ACTIVITIES = [
  { id: "a1", title: "Grenoble to Bourg d'Oisans", date: "2024-07-15", distance_km: 65, elevation_m: 1200, time_hours: 4.5 },
  { id: "a2", title: "Col du Galibier", date: "2024-07-16", distance_km: 92, elevation_m: 3100, time_hours: 7.2 },
  { id: "a3", title: "Briançon Loop", date: "2024-07-17", distance_km: 78, elevation_m: 2400, time_hours: 5.8 },
  { id: "a4", title: "Col d'Izoard", date: "2024-07-18", distance_km: 105, elevation_m: 3200, time_hours: 6.5 },
  { id: "a5", title: "Return to Grenoble", date: "2024-07-19", distance_km: 83, elevation_m: 2550, time_hours: 4.5 },
];

const SINGLE_DAY_ACTIVITIES = [
  { id: "r1", title: "Bern Grand Prix", date: "2024-08-10", distance_km: 52, elevation_m: 320, time_hours: 1.5 },
];

const MULTI_DAY_JOURNAL_ENTRIES = [
  {
    date: "2024-07-15",
    description: "First day on the road! Left Grenoble early to beat the heat. The climb to Bourg d'Oisans was gentle, perfect warmup for what's to come.",
    activity_ids: ["a1"],
    photos: ["https://images.unsplash.com/photo-1541625602330-2277a4c46182?w=400"],
    links: [{ title: "Hotel & Campground", type: "place", url: "#" }],
  },
  {
    date: "2024-07-16",
    description: "The big one! Col du Galibier at 2,642m. Started at 5am to avoid afternoon storms. The last 5km were brutal but the views... incredible.",
    activity_ids: ["a2"],
    photos: [
      "https://images.unsplash.com/photo-1517649763962-0c623066013b?w=400",
      "https://images.unsplash.com/photo-1534787238916-9ba6764efd4f?w=400",
    ],
    links: [],
  },

  {
    date: "2024-07-17",
    description: "Rest day turned into an impromptu loop. Found an amazing bakery in Briançon - best croissants of the trip!",
    activity_ids: ["a3"],
    photos: [],
    links: [{ title: "La Boulangerie du Col", type: "place", url: "#" }],
  },
  {
    date: "2024-07-18",
    description: "Col d'Izoard and the legendary Casse Déserte. The lunar landscape is surreal. Stopped for countless photos.",
    activity_ids: ["a4"],
    photos: [
      "https://images.unsplash.com/photo-1507035895480-2b3156c31fc8?w=400",
      "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400",
      "https://images.unsplash.com/photo-1571188654248-7a89213915f7?w=400",
    ],
    links: [
      { title: "Casse Déserte Info", type: "article", url: "#" },
      { title: "Komoot Route", type: "route", url: "#" },
    ],
  },
  {
    date: "2024-07-19",
    description: "Final push back to Grenoble. Bittersweet ending to an unforgettable adventure.",
    activity_ids: ["a5"],
    photos: ["https://images.unsplash.com/photo-1471506480208-91b3a4cc78be?w=400"],
    links: [],
  },
];

const SINGLE_DAY_JOURNAL_ENTRIES = [
  {
    date: "2024-08-10",
    description: "Great race despite the mechanical! Lost the chain in lap 15 and had to chase back for 3 laps. Managed to bridge to the second group and held on for 12th place. Next year I'm going for the podium.",
    activity_ids: ["r1"],
    photos: [
      "https://images.unsplash.com/photo-1517649763962-0c623066013b?w=400",
      "https://images.unsplash.com/photo-1534787238916-9ba6764efd4f?w=400",
    ],
    links: [{ title: "Race Results", type: "article", url: "#" }],
  },
];

const MULTI_DAY_EVENT_LINKS = [
  { title: "Full Route on Komoot", type: "route", url: "#" },
  { title: "Gear List", type: "gear", url: "#" },
  { title: "Trip Planning Article", type: "article", url: "#" },
];

const SINGLE_DAY_EVENT_LINKS = [
  { title: "Race Website", type: "article", url: "#" },
  { title: "Strava Segment", type: "route", url: "#" },
];

// Type definitions
type ActivityType = { id: string; title: string; date: string; distance_km: number; elevation_m: number; time_hours: number };


// Helper components
function EventTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    race: "bg-red-500/20 text-red-600",
    tour: "bg-blue-500/20 text-blue-600",
    bikepacking: "bg-emerald-500/20 text-emerald-600",
    event: "bg-purple-500/20 text-purple-600",
    other: "bg-muted text-muted-foreground",
  };
  return (
    <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium capitalize", colors[type] || colors.other)}>
      {type}
    </span>
  );
}

function LinkIcon({ type }: { type: string }) {
  const icons: Record<string, string> = {
    route: "M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7",
    place: "M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z",
    article: "M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z",
    video: "M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    gear: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
    other: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
  };
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icons[type] || icons.other} />
    </svg>
  );
}


function StatCard({ label, value, unit }: { label: string; value: number | string; unit?: string }) {
  return (
    <div className="text-center">
      <div className="text-metric">{value}{unit && <span className="text-lg ml-0.5">{unit}</span>}</div>
      <div className="text-metric-label">{label}</div>
    </div>
  );
}

function ActivityCard({ activity }: { activity: ActivityType }) {
  return (
    <div className="flex items-center gap-4 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors cursor-pointer">
      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
        <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{activity.title}</div>
        <div className="text-caption">{activity.distance_km} km · {activity.elevation_m}m · {activity.time_hours}h</div>
      </div>
    </div>
  );
}

function PhotoGallery({ photos }: { photos: string[] }) {
  if (photos.length === 0) return null;
  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {photos.map((url, i) => (
        <img key={i} src={url} alt="" className="w-24 h-24 object-cover rounded-lg flex-shrink-0" />
      ))}
    </div>
  );
}

function LinksList({ links }: { links: { title: string; type: string; url: string }[] }) {
  if (links.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {links.map((link, i) => (
        <a key={i} href={link.url} className="inline-flex items-center gap-1.5 px-2 py-1 bg-muted rounded text-sm hover:bg-muted/80">
          <LinkIcon type={link.type} />
          {link.title}
        </a>
      ))}
    </div>
  );
}


// ============================================================================
// VARIANT 1: Full-width hero cover, stats in overlay
// ============================================================================
function Variant1({ event, stats, activities, journalEntries, eventLinks }: {
  event: typeof MULTI_DAY_EVENT | typeof SINGLE_DAY_EVENT;
  stats: typeof MULTI_DAY_STATS | typeof SINGLE_DAY_STATS;
  activities: typeof MULTI_DAY_ACTIVITIES | typeof SINGLE_DAY_ACTIVITIES;
  journalEntries: typeof MULTI_DAY_JOURNAL_ENTRIES | typeof SINGLE_DAY_JOURNAL_ENTRIES;
  eventLinks: typeof MULTI_DAY_EVENT_LINKS | typeof SINGLE_DAY_EVENT_LINKS;
}) {
  const isSingleDay = event.start_date === event.end_date;
  
  return (
    <div className="-m-6">
      {/* Full-width hero with overlay */}
      <div className="relative h-80 overflow-hidden">
        <img src={event.cover_image_url} alt="" className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-6 text-white">
          <div className="max-w-4xl mx-auto">
            <EventTypeBadge type={event.event_type} />
            <h1 className="text-3xl font-bold mt-2">{event.title}</h1>
            <p className="text-white/80 mt-1">
              {isSingleDay 
                ? new Date(event.start_date).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
                : `${new Date(event.start_date).toLocaleDateString()} – ${new Date(event.end_date).toLocaleDateString()}`
              }
            </p>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div className="bg-card border-b border-border">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className={cn("grid gap-4", isSingleDay ? "grid-cols-4" : "grid-cols-5")}>
            <StatCard label="Distance" value={stats.total_distance_km} unit="km" />
            <StatCard label="Elevation" value={stats.total_elevation_m < 1000 ? stats.total_elevation_m : (stats.total_elevation_m / 1000).toFixed(1)} unit={stats.total_elevation_m < 1000 ? "m" : "k"} />
            <StatCard label="Time" value={stats.total_time_hours < 10 ? stats.total_time_hours.toFixed(1) : Math.round(stats.total_time_hours)} unit="h" />
            {!isSingleDay && <StatCard label="Activities" value={stats.total_activities} />}
            <StatCard label="Photos" value={stats.total_photos} />
          </div>
        </div>
      </div>


      {/* Content */}
      <div className="max-w-4xl mx-auto px-6 py-6 space-y-8">
        {/* Description */}
        <div className="prose prose-sm max-w-none text-foreground">
          {event.description.split('\n\n').map((p, i) => <p key={i}>{p}</p>)}
        </div>

        {/* Event links */}
        <LinksList links={eventLinks} />

        {/* Timeline - simplified for single day */}
        {isSingleDay ? (
          // Single day: no "Day by Day" header, just the content
          <div className="space-y-4">
            {journalEntries.map((entry, i) => {
              const entryActivities = activities.filter(a => entry.activity_ids.includes(a.id));
              return (
                <div key={i} className="space-y-4">
                  {/* Activities */}
                  {entryActivities.map(a => <ActivityCard key={a.id} activity={a} />)}
                  
                  {/* Journal text */}
                  {entry.description && <p className="text-body">{entry.description}</p>}
                  
                  {/* Photos */}
                  <PhotoGallery photos={entry.photos} />
                  
                  {/* Links */}
                  <LinksList links={entry.links} />
                </div>
              );
            })}
          </div>
        ) : (
          // Multi-day: full timeline
          <div className="space-y-6">
            <h2 className="text-card-title">Day by Day</h2>
            {journalEntries.map((entry, i) => {
              const entryActivities = activities.filter(a => entry.activity_ids.includes(a.id));
              return (
                <div key={i} className="relative pl-8 pb-6 border-l-2 border-border last:border-l-0 last:pb-0">
                  {/* Day marker */}
                  <div className="absolute left-0 top-0 -translate-x-1/2 w-4 h-4 rounded-full bg-primary border-4 border-background" />
                  <div className="text-sm font-medium text-muted-foreground mb-2">
                    Day {i + 1} · {new Date(entry.date).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
                  </div>
                  
                  {/* Activities */}
                  <div className="space-y-2 mb-3">
                    {entryActivities.map(a => <ActivityCard key={a.id} activity={a} />)}
                  </div>
                  
                  {/* Journal text */}
                  {entry.description && <p className="text-body mb-3">{entry.description}</p>}
                  
                  {/* Photos */}
                  <PhotoGallery photos={entry.photos} />
                  
                  {/* Links */}
                  <div className="mt-2">
                    <LinksList links={entry.links} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


// ============================================================================
// VARIANT 2: Contained card layout, cover as large image in header
// ============================================================================
function Variant2() {
  return (
    <div className="p-6 space-y-6">
      {/* Header card with cover */}
      <Card>
        <div className="relative h-48 overflow-hidden rounded-t-lg">
          <img src={MULTI_DAY_EVENT.cover_image_url} alt="" className="w-full h-full object-cover" />
        </div>
        <CardContent className="pt-4 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <EventTypeBadge type={MULTI_DAY_EVENT.event_type} />
              </div>
              <h1 className="text-page-title">{MULTI_DAY_EVENT.title}</h1>
              <p className="text-page-subtitle">
                {new Date(MULTI_DAY_EVENT.start_date).toLocaleDateString()} – {new Date(MULTI_DAY_EVENT.end_date).toLocaleDateString()}
              </p>
            </div>
            <Button variant="outline" size="sm">Edit</Button>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-5 gap-4 py-4 border-y border-border">
            <StatCard label="Distance" value={MULTI_DAY_STATS.total_distance_km} unit="km" />
            <StatCard label="Elevation" value={(MULTI_DAY_STATS.total_elevation_m / 1000).toFixed(1)} unit="k" />
            <StatCard label="Time" value={MULTI_DAY_STATS.total_time_hours.toFixed(1)} unit="h" />
            <StatCard label="Activities" value={MULTI_DAY_STATS.total_activities} />
            <StatCard label="Photos" value={MULTI_DAY_STATS.total_photos} />
          </div>

          {/* Description */}
          <div className="prose prose-sm max-w-none text-foreground">
            {MULTI_DAY_EVENT.description.split('\n\n').map((p, i) => <p key={i}>{p}</p>)}
          </div>

          {/* Links */}
          <LinksList links={MULTI_DAY_EVENT_LINKS} />
        </CardContent>
      </Card>


      {/* Timeline as separate cards per day */}
      <div className="space-y-4">
        <h2 className="text-card-title">Day by Day</h2>
        {MULTI_DAY_JOURNAL_ENTRIES.map((entry, i) => {
          const activities = MULTI_DAY_ACTIVITIES.filter(a => entry.activity_ids.includes(a.id));
          return (
            <Card key={i}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center justify-between">
                  <span>Day {i + 1}</span>
                  <span className="text-caption font-normal">
                    {new Date(entry.date).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Activities */}
                {activities.map(a => <ActivityCard key={a.id} activity={a} />)}
                
                {/* Journal text */}
                {entry.description && <p className="text-body">{entry.description}</p>}
                
                {/* Photos */}
                <PhotoGallery photos={entry.photos} />
                
                {/* Links */}
                <LinksList links={entry.links} />
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}


// ============================================================================
// VARIANT 3: Two-column layout (sidebar with info, main with timeline)
// ============================================================================
function Variant3() {
  return (
    <div className="p-6">
      <div className="grid grid-cols-3 gap-6">
        {/* Sidebar */}
        <div className="space-y-4">
          {/* Cover & title */}
          <Card>
            <div className="relative h-40 overflow-hidden rounded-t-lg">
              <img src={MULTI_DAY_EVENT.cover_image_url} alt="" className="w-full h-full object-cover" />
            </div>
            <CardContent className="pt-3">
              <EventTypeBadge type={MULTI_DAY_EVENT.event_type} />
              <h1 className="text-xl font-bold mt-2">{MULTI_DAY_EVENT.title}</h1>
              <p className="text-caption mt-1">
                {new Date(MULTI_DAY_EVENT.start_date).toLocaleDateString()} – {new Date(MULTI_DAY_EVENT.end_date).toLocaleDateString()}
              </p>
            </CardContent>
          </Card>

          {/* Stats */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Distance</span>
                <span className="font-medium">{MULTI_DAY_STATS.total_distance_km} km</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Elevation</span>
                <span className="font-medium">{MULTI_DAY_STATS.total_elevation_m.toLocaleString()} m</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Time</span>
                <span className="font-medium">{MULTI_DAY_STATS.total_time_hours} hours</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Activities</span>
                <span className="font-medium">{MULTI_DAY_STATS.total_activities}</span>
              </div>
            </CardContent>
          </Card>


          {/* Links */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Links</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {MULTI_DAY_EVENT_LINKS.map((link, i) => (
                <a key={i} href={link.url} className="flex items-center gap-2 text-sm hover:text-primary">
                  <LinkIcon type={link.type} />
                  {link.title}
                </a>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Main content - Timeline */}
        <div className="col-span-2 space-y-4">
          {/* Description */}
          <Card>
            <CardContent className="pt-4">
              <div className="prose prose-sm max-w-none text-foreground">
                {MULTI_DAY_EVENT.description.split('\n\n').map((p, i) => <p key={i}>{p}</p>)}
              </div>
            </CardContent>
          </Card>

          {/* Timeline */}
          {MULTI_DAY_JOURNAL_ENTRIES.map((entry, i) => {
            const activities = MULTI_DAY_ACTIVITIES.filter(a => entry.activity_ids.includes(a.id));
            return (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">
                    Day {i + 1} · {new Date(entry.date).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {activities.map(a => <ActivityCard key={a.id} activity={a} />)}
                  {entry.description && <p className="text-body">{entry.description}</p>}
                  <PhotoGallery photos={entry.photos} />
                  <LinksList links={entry.links} />
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}


// ============================================================================
// VARIANT SWITCHER & EXPORT
// ============================================================================
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

function DataSwitcher({ isSingleDay, onChange }: { isSingleDay: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="fixed bottom-16 left-1/2 -translate-x-1/2 bg-card border border-border rounded-lg shadow-lg p-2 flex gap-2 z-50">
      <button
        onClick={() => onChange(false)}
        className={cn(
          "px-3 py-1.5 rounded text-sm font-medium transition-colors",
          !isSingleDay ? "bg-emerald-600 text-white" : "hover:bg-muted"
        )}
      >
        Multi-day Trip
      </button>
      <button
        onClick={() => onChange(true)}
        className={cn(
          "px-3 py-1.5 rounded text-sm font-medium transition-colors",
          isSingleDay ? "bg-red-600 text-white" : "hover:bg-muted"
        )}
      >
        Single-day Race
      </button>
    </div>
  );
}

export function PrototypeEventDetail() {
  const [searchParams, setSearchParams] = useSearchParams();
  const variant = parseInt(searchParams.get("variant") || "1", 10);
  const isSingleDay = searchParams.get("single") === "true";

  const setVariant = (v: number) => {
    setSearchParams({ variant: v.toString(), single: isSingleDay.toString() });
  };
  
  const setSingleDay = (single: boolean) => {
    setSearchParams({ variant: variant.toString(), single: single.toString() });
  };

  // Select data based on mode
  const event = isSingleDay ? SINGLE_DAY_EVENT : MULTI_DAY_EVENT;
  const stats = isSingleDay ? SINGLE_DAY_STATS : MULTI_DAY_STATS;
  const activities = isSingleDay ? SINGLE_DAY_ACTIVITIES : MULTI_DAY_ACTIVITIES;
  const journalEntries = isSingleDay ? SINGLE_DAY_JOURNAL_ENTRIES : MULTI_DAY_JOURNAL_ENTRIES;
  const eventLinks = isSingleDay ? SINGLE_DAY_EVENT_LINKS : MULTI_DAY_EVENT_LINKS;

  return (
    <>
      {variant === 1 && <Variant1 event={event} stats={stats} activities={activities} journalEntries={journalEntries} eventLinks={eventLinks} />}
      {variant === 2 && <Variant2 />}
      {variant === 3 && <Variant3 />}
      <DataSwitcher isSingleDay={isSingleDay} onChange={setSingleDay} />
      <VariantSwitcher current={variant} onChange={setVariant} />
    </>
  );
}
