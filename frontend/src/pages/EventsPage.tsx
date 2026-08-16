/**
 * Events List Page
 * 
 * Displays user's ride events (races, tours, bikepacking trips) with filtering and sorting.
 * Based on prototype: Large cards with image overlay + filter/sort bar
 */

import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatEventDateRange } from "@/lib/event-utils";
import { fetchEvents } from "@/api/events";
import type { PaginatedEvents } from "@/api/events";

// Extended event type with stats for display
interface EventWithStats {
  id: string;
  title: string;
  event_type: string;
  start_date: string;
  end_date: string | null;
  cover_image_url?: string | null;
  // Stats from API
  total_distance_km?: number | null;
  total_elevation_m?: number | null;
  total_activities?: number;
  total_photos?: number;
}

function EventTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    race: "bg-red-500/20 text-red-400 border-red-500/30",
    tour: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    bikepacking: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    event: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    other: "bg-muted text-muted-foreground border-border",
  };
  return (
    <span className={cn(
      "px-2 py-0.5 text-xs rounded-full font-medium capitalize border",
      colors[type] || colors.other
    )}>
      {type}
    </span>
  );
}

function PlusIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function EmptyState({ onCreateEvent }: { onCreateEvent: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-32 h-32 mb-6 rounded-full bg-muted flex items-center justify-center">
        <svg className="w-16 h-16 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      
      <h2 className="text-xl font-semibold mb-2">No events yet</h2>
      <p className="text-muted-foreground mb-6 max-w-sm">
        Mark your special rides — races, tours, or bikepacking trips — with photos, notes, and memories.
      </p>
      
      <Button size="lg" onClick={onCreateEvent}>
        <PlusIcon />
        <span className="ml-2">Create Your First Event</span>
      </Button>
    </div>
  );
}

function EventCard({ event }: { event: EventWithStats }) {
  // Generate gradient placeholder for events without cover
  const gradients = [
    "from-blue-600 to-purple-600",
    "from-emerald-600 to-teal-600",
    "from-orange-600 to-red-600",
    "from-pink-600 to-rose-600",
    "from-indigo-600 to-blue-600",
  ];
  const gradientIndex = event.id.charCodeAt(0) % gradients.length;
  
  const hasCover = event.cover_image_url;
  const totalActivities = event.total_activities ?? 0;
  const totalPhotos = event.total_photos ?? 0;
  
  return (
    <Link to={`/events/${event.id}`} className="group block">
      <Card className="overflow-hidden hover:border-primary/50 transition-colors">
        <div className="relative aspect-[16/10] overflow-hidden">
          {hasCover ? (
            <img 
              src={event.cover_image_url!} 
              alt="" 
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" 
            />
          ) : (
            <div className={cn(
              "w-full h-full bg-gradient-to-br group-hover:scale-105 transition-transform duration-300",
              gradients[gradientIndex]
            )} />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
          
          <div className="absolute top-3 left-3">
            <EventTypeBadge type={event.event_type} />
          </div>
          
          <div className="absolute bottom-0 left-0 right-0 p-4 text-white">
            <h3 className="font-semibold text-lg leading-tight group-hover:text-primary transition-colors">
              {event.title}
            </h3>
            <p className="text-white/70 text-sm mt-1">
              {formatEventDateRange(event.start_date, event.end_date)}
            </p>
          </div>
        </div>
        
        <CardContent className="py-3 px-4">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>{event.total_distance_km ? `${Math.round(event.total_distance_km)} km` : "—"}</span>
            <span>{event.total_elevation_m ? `${event.total_elevation_m.toLocaleString()} m` : "—"}</span>
            <span>{totalActivities} {totalActivities === 1 ? 'ride' : 'rides'}</span>
            <span>{totalPhotos} photos</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function EventCardSkeleton() {
  return (
    <Card className="overflow-hidden">
      <Skeleton className="aspect-[16/10]" />
      <CardContent className="py-3 px-4">
        <div className="flex justify-between">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-12" />
        </div>
      </CardContent>
    </Card>
  );
}

// Event types matching the prototype
const EVENT_TYPES = [
  { value: "all", label: "All" },
  { value: "race", label: "Race" },
  { value: "tour", label: "Tour" },
  { value: "bikepacking", label: "Bikepacking" },
  { value: "event", label: "Event" },
];

export function EventsPage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedEvents | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const perPage = 12;

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchEvents(page, perPage, filter === "all" ? undefined : filter)
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [filter, page, perPage]);

  const handleCreateEvent = () => {
    navigate("/events/new");
  };

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          Failed to load events: {error}
        </div>
      </div>
    );
  }

  const events = data?.events || [];
  const pagination = data?.pagination;
  const isEmpty = !isLoading && events.length === 0 && filter === "all";

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-page-title">Events</h1>
          <p className="text-body-secondary mt-2">Your races, tours, and adventures</p>
        </div>
        {!isEmpty && (
          <Button onClick={handleCreateEvent}>
            <PlusIcon />
            <span className="ml-2">Create Event</span>
          </Button>
        )}
      </div>

      {isEmpty ? (
        <EmptyState onCreateEvent={handleCreateEvent} />
      ) : (
        <>
          {/* Filter bar */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Type:</span>
            <div className="flex gap-1">
              {EVENT_TYPES.map(type => (
                <button
                  key={type.value}
                  onClick={() => {
                    setFilter(type.value);
                    setPage(1);
                  }}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-lg transition-colors capitalize",
                    filter === type.value 
                      ? "bg-primary text-primary-foreground" 
                      : "bg-muted hover:bg-muted/80"
                  )}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          {/* Loading state */}
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {Array.from({ length: 6 }).map((_, i) => (
                <EventCardSkeleton key={i} />
              ))}
            </div>
          ) : (
            <>
              {/* Card grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {events.map(event => (
                  <EventCard key={event.id} event={event as EventWithStats} />
                ))}
              </div>

              {/* Empty filter result */}
              {events.length === 0 && filter !== "all" && (
                <div className="text-center py-12 text-muted-foreground">
                  No {filter} events found.
                </div>
              )}

              {/* Pagination */}
              {pagination && pagination.total_pages > 1 && (
                <div className="flex justify-center gap-2 pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    Previous
                  </Button>
                  <span className="flex items-center px-4 text-sm text-muted-foreground">
                    Page {page} of {pagination.total_pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= pagination.total_pages}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
