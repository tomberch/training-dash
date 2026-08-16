/**
 * Event Detail Page
 * 
 * Displays a single event with hero, stats, journal entries, photos, and linked activities.
 * View-only page - editing is done on EventEditPage.
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { fetchEvent, deleteEvent } from "@/api/events";
import type { EventDetail, EventMedia, EventLink, JournalEntryActivity } from "@/api/events";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import { formatEventDuration, isSingleDayEvent, formatEventHeaderDates } from "@/lib/event-utils";
import { EventTourMap } from "@/components/EventTourMap";
import Lightbox from "yet-another-react-lightbox";
import "yet-another-react-lightbox/styles.css";

// Custom styles for more visible navigation arrows
const lightboxStyles = {
  button: {
    filter: "drop-shadow(0 0 4px rgba(0, 0, 0, 0.9))",
    background: "rgba(0, 0, 0, 0.4)",
    borderRadius: "50%",
    padding: "8px",
    margin: "16px",
  },
  icon: {
    width: 32,
    height: 32,
    color: "white",
  },
};

function MarkdownDisplay({ source, className }: { source: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{source}</ReactMarkdown>
    </div>
  );
}

function EventTypeBadge({ type, light = false }: { type: string; light?: boolean }) {
  const colors: Record<string, string> = light ? {
    race: "bg-white/20 text-white",
    tour: "bg-white/20 text-white",
    bikepacking: "bg-white/20 text-white",
    event: "bg-white/20 text-white",
    other: "bg-white/20 text-white",
  } : {
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

function ActivityCard({ activity }: { activity: JournalEntryActivity }) {
  const details = activity.activity;
  const title = details?.title || "Untitled Activity";
  const stats: string[] = [];
  
  if (details?.distance_km) stats.push(`${details.distance_km} km`);
  if (details?.elevation_m) stats.push(`${details.elevation_m}m`);
  if (details?.duration_seconds) stats.push(formatEventDuration(details.duration_seconds));
  
  return (
    <Link
      to={`/activities/${activity.activity_id}`}
      className="flex items-center gap-4 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
    >
      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
        <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{title}</div>
        <div className="text-caption">{stats.length > 0 ? stats.join(" · ") : "View details"}</div>
      </div>
    </Link>
  );
}

function PhotoGallery({ photos }: { photos: EventMedia[] }) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  if (photos.length === 0) return null;

  const slides = photos.map((media) => ({
    src: media.storage_path,
    alt: media.caption || "",
  }));

  return (
    <>
      <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
        {photos.map((media: EventMedia, index: number) => (
          <button
            key={media.id}
            type="button"
            className="aspect-square cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-lg"
            onClick={() => {
              setLightboxIndex(index);
              setLightboxOpen(true);
            }}
          >
            <img
              src={media.thumbnail_path || media.storage_path}
              alt={media.caption || ""}
              loading="lazy"
              className="w-full h-full object-cover rounded-lg hover:opacity-90 transition-opacity"
            />
          </button>
        ))}
      </div>
      <Lightbox
        open={lightboxOpen}
        close={() => setLightboxOpen(false)}
        index={lightboxIndex}
        slides={slides}
        styles={lightboxStyles}
      />
    </>
  );
}

function LinksList({ links }: { links: EventLink[] }) {
  if (links.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {links.map((link: EventLink) => (
        <a
          key={link.id}
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-muted rounded-lg text-sm hover:bg-muted/80 transition-colors"
        >
          <LinkIcon type={link.link_type} />
          {link.title}
        </a>
      ))}
    </div>
  );
}

export function EventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchEvent(id)
      .then(setEvent)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id]);

  const handleDelete = async () => {
    if (!id) return;
    setIsDeleting(true);
    try {
      await deleteEvent(id);
      toast.success("Event deleted");
      navigate("/events");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete event");
    } finally {
      setIsDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  if (!id) {
    return <div className="p-6">Event not found</div>;
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          Failed to load event: {error}
        </div>
      </div>
    );
  }

  if (isLoading || !event) {
    return (
      <div className="p-8">
        <Skeleton className="h-6 w-32 mb-4" />
        <Skeleton className="h-80 w-full rounded-xl mb-6" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  const isSingleDay = isSingleDayEvent(event.start_date, event.end_date);
  const stats = event.stats;
  const coverMedia = event.cover_image_id ? event.media.find(m => m.id === event.cover_image_id) : null;
  
  const gradients = [
    "from-blue-600 to-purple-600",
    "from-emerald-600 to-teal-600",
    "from-orange-600 to-red-600",
    "from-pink-600 to-rose-600",
    "from-indigo-600 to-blue-600",
  ];
  const gradientIndex = event.id.charCodeAt(0) % gradients.length;

  const allPhotos = [
    ...event.media.filter((m: EventMedia) => m.media_type === "photo"),
    ...event.entries.flatMap(e => e.media.filter((m: EventMedia) => m.media_type === "photo"))
  ];

  const allVideos = [
    ...event.media.filter((m: EventMedia) => m.media_type === "video"),
    ...event.entries.flatMap(e => e.media.filter((m: EventMedia) => m.media_type === "video"))
  ];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <button 
            onClick={() => navigate("/events")} 
            className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 hover:underline"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to events
          </button>
          
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => navigate(`/events/${id}/edit`)} title="Edit">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </Button>
            <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="icon" className="text-destructive hover:text-destructive hover:bg-destructive/10" title="Delete">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete Event</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to delete "{event.title}"? This will also delete all journal entries, photos, and links. Activities will be unlinked but not deleted.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDelete}
                    disabled={isDeleting}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {isDeleting ? "Deleting..." : "Delete"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </div>

      {/* Hero */}
      <div className="relative aspect-[21/9] rounded-xl overflow-hidden mb-8">
        {coverMedia ? (
          <img src={coverMedia.storage_path} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className={cn("w-full h-full bg-gradient-to-br", gradients[gradientIndex])} />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-6 text-white">
          <EventTypeBadge type={event.event_type} light />
          <h1 className="text-3xl font-bold mt-2">{event.title}</h1>
          <p className="text-white/80 mt-1">{formatEventHeaderDates(event.start_date, event.end_date)}</p>
        </div>
      </div>

      {/* Stats bar */}
      <div className="bg-card border border-border rounded-xl p-4 mb-8">
        <div className={cn("grid gap-4", isSingleDay ? "grid-cols-4" : "grid-cols-5")}>
          <StatCard label="Distance" value={stats.total_distance_km ? Math.round(stats.total_distance_km) : "—"} unit={stats.total_distance_km ? "km" : undefined} />
          <StatCard label="Elevation" value={stats.total_elevation_m ? (stats.total_elevation_m < 1000 ? Math.round(stats.total_elevation_m) : (stats.total_elevation_m / 1000).toFixed(1)) : "—"} unit={stats.total_elevation_m ? (stats.total_elevation_m < 1000 ? "m" : "k") : undefined} />
          <StatCard label="Time" value={stats.total_duration_seconds ? (stats.total_duration_seconds < 36000 ? (stats.total_duration_seconds / 3600).toFixed(1) : Math.round(stats.total_duration_seconds / 3600)) : "—"} unit={stats.total_duration_seconds ? "h" : undefined} />
          {!isSingleDay && <StatCard label="Activities" value={stats.activity_count} />}
          <StatCard label="Photos" value={allPhotos.length} />
        </div>
      </div>

      {/* Content sections */}
      <div className="space-y-8">
        {event.description && (
          <section>
            <MarkdownDisplay source={event.description} className="prose prose-sm max-w-none text-foreground prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-a:text-primary" />
          </section>
        )}

        {/* Tour Map - shows all activities across all days */}
        <EventTourMap entries={event.entries} isSingleDay={isSingleDay} />

        {event.links.length > 0 && (
          <section>
            <h2 className="text-card-title mb-3">Links</h2>
            <LinksList links={event.links} />
          </section>
        )}

        {allPhotos.length > 0 && (
          <section>
            <h2 className="text-card-title mb-3">Photos</h2>
            <PhotoGallery photos={allPhotos} />
          </section>
        )}

        {allVideos.length > 0 && (
          <section>
            <h2 className="text-card-title mb-3">Videos</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {allVideos.map((video: EventMedia) => (
                <a key={video.id} href={video.storage_path} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 p-3 bg-muted rounded-lg hover:bg-muted/80 transition-colors">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <span className="font-medium">{video.caption || "Video"}</span>
                </a>
              ))}
            </div>
          </section>
        )}

        {!isSingleDay && event.entries.length > 0 && (
          <section>
            <h2 className="text-card-title mb-4">Day by Day</h2>
            <div className="space-y-6">
              {event.entries.map((entry, i: number) => (
                <div key={entry.id} className="relative pl-8 pb-6 border-l-2 border-border last:border-l-0 last:pb-0">
                  <div className="absolute left-0 top-0 -translate-x-1/2 w-4 h-4 rounded-full bg-primary border-4 border-background" />
                  <div className="text-sm font-medium text-muted-foreground mb-2">
                    Day {i + 1} · {new Date(entry.entry_date).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
                  </div>
                  {entry.activities.length > 0 && (
                    <div className="space-y-2 mb-3">
                      {entry.activities.map((a: JournalEntryActivity) => <ActivityCard key={a.id} activity={a} />)}
                    </div>
                  )}
                  {entry.description && <MarkdownDisplay source={entry.description} className="prose prose-sm max-w-none text-foreground mb-3" />}
                  {entry.media.filter((m: EventMedia) => m.media_type === "photo").length > 0 && (
                    <div className="mt-3"><PhotoGallery photos={entry.media.filter((m: EventMedia) => m.media_type === "photo")} /></div>
                  )}
                  {entry.links.length > 0 && <div className="mt-2"><LinksList links={entry.links} /></div>}
                </div>
              ))}
            </div>
          </section>
        )}

        {isSingleDay && event.entries.some(e => e.activities.length > 0) && (
          <section>
            <h2 className="text-card-title mb-3">Activities</h2>
            <div className="space-y-2">
              {event.entries.flatMap(entry => entry.activities.map((a: JournalEntryActivity) => <ActivityCard key={a.id} activity={a} />))}
            </div>
          </section>
        )}

        {isSingleDay && event.entries.some(e => e.description) && (
          <section>
            {event.entries.filter(e => e.description).map(entry => (
              <MarkdownDisplay key={entry.id} source={entry.description!} className="prose prose-sm max-w-none text-foreground" />
            ))}
          </section>
        )}

        {allPhotos.length === 0 && event.entries.length === 0 && !event.description && event.links.length === 0 && (
          <div className="text-center py-12 text-muted-foreground border border-dashed border-border rounded-xl">
            <p className="mb-4">No content yet. Add photos, journal entries, and activities.</p>
            <Button variant="outline" onClick={() => navigate(`/events/${id}/edit`)}>Edit Event</Button>
          </div>
        )}
      </div>
    </div>
  );
}
