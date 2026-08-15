/**
 * PROTOTYPE: Event List Page
 * 
 * Selected layout: Large cards with image overlay + filter/sort bar
 * View at: /prototype/event-list
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Mock events data
const MOCK_EVENTS = [
  {
    id: "1",
    title: "Alps Bikepacking 2024",
    event_type: "bikepacking",
    start_date: "2024-07-15",
    end_date: "2024-07-19",
    cover_image_url: "https://images.unsplash.com/photo-1507035895480-2b3156c31fc8?w=600",
    total_distance_km: 423,
    total_elevation_m: 12450,
    total_activities: 5,
    total_photos: 47,
  },
  {
    id: "2",
    title: "Bern Grand Prix 2024",
    event_type: "race",
    start_date: "2024-08-10",
    end_date: "2024-08-10",
    cover_image_url: "https://images.unsplash.com/photo-1517649763962-0c623066013b?w=600",
    total_distance_km: 52,
    total_elevation_m: 320,
    total_activities: 1,
    total_photos: 8,
  },
  {
    id: "3",
    title: "Flanders Classics Weekend",
    event_type: "tour",
    start_date: "2024-04-05",
    end_date: "2024-04-07",
    cover_image_url: "https://images.unsplash.com/photo-1541625602330-2277a4c46182?w=600",
    total_distance_km: 285,
    total_elevation_m: 3200,
    total_activities: 3,
    total_photos: 23,
  },
  {
    id: "4",
    title: "Local Club Race Series",
    event_type: "race",
    start_date: "2024-06-22",
    end_date: "2024-06-22",
    cover_image_url: "https://images.unsplash.com/photo-1534787238916-9ba6764efd4f?w=600",
    total_distance_km: 68,
    total_elevation_m: 450,
    total_activities: 1,
    total_photos: 5,
  },
  {
    id: "5",
    title: "Pyrenees Gran Fondo",
    event_type: "event",
    start_date: "2024-09-14",
    end_date: "2024-09-15",
    cover_image_url: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600",
    total_distance_km: 210,
    total_elevation_m: 5800,
    total_activities: 2,
    total_photos: 31,
  },
  {
    id: "6",
    title: "Dolomites Adventure",
    event_type: "bikepacking",
    start_date: "2024-08-25",
    end_date: "2024-08-31",
    cover_image_url: "https://images.unsplash.com/photo-1571188654248-7a89213915f7?w=600",
    total_distance_km: 520,
    total_elevation_m: 15200,
    total_activities: 7,
    total_photos: 89,
  },
];

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

function formatDateRange(start: string, end: string) {
  const s = new Date(start);
  const e = new Date(end);
  
  if (start === end) {
    return s.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
  
  if (s.getFullYear() === e.getFullYear()) {
    if (s.getMonth() === e.getMonth()) {
      return `${s.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${e.getDate()}, ${e.getFullYear()}`;
    }
    return `${s.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${e.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`;
  }
  
  return `${s.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })} – ${e.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}`;
}

function PlusIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function EmptyState() {
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
      
      <Button size="lg">
        <PlusIcon />
        <span className="ml-2">Create Your First Event</span>
      </Button>
    </div>
  );
}

export function PrototypeEventList() {
  const [filter, setFilter] = useState<string>("all");
  const [sort, setSort] = useState<string>("date-desc");
  const [showEmpty, setShowEmpty] = useState(false);
  
  const events = showEmpty ? [] : MOCK_EVENTS;
  
  const filteredEvents = filter === "all" 
    ? events 
    : events.filter(e => e.event_type === filter);
  
  const sortedEvents = [...filteredEvents].sort((a, b) => {
    if (sort === "date-desc") return new Date(b.start_date).getTime() - new Date(a.start_date).getTime();
    if (sort === "date-asc") return new Date(a.start_date).getTime() - new Date(b.start_date).getTime();
    if (sort === "distance") return b.total_distance_km - a.total_distance_km;
    return 0;
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-page-title">Events</h1>
          <p className="text-body-secondary mt-2">Your races, tours, and adventures</p>
        </div>
        <Button>
          <PlusIcon />
          <span className="ml-2">Create Event</span>
        </Button>
      </div>

      {events.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {/* Filter/Sort bar */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Type:</span>
              <div className="flex gap-1">
                {["all", "race", "tour", "bikepacking", "event"].map(type => (
                  <button
                    key={type}
                    onClick={() => setFilter(type)}
                    className={cn(
                      "px-3 py-1.5 text-sm rounded-lg transition-colors capitalize",
                      filter === type 
                        ? "bg-primary text-primary-foreground" 
                        : "bg-muted hover:bg-muted/80"
                    )}
                  >
                    {type === "all" ? "All" : type}
                  </button>
                ))}
              </div>
            </div>
            
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-sm text-muted-foreground">Sort:</span>
              <select 
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                className="px-3 py-1.5 text-sm rounded-lg bg-muted border-0 focus:ring-2 focus:ring-primary"
              >
                <option value="date-desc">Newest first</option>
                <option value="date-asc">Oldest first</option>
                <option value="distance">By distance</option>
              </select>
            </div>
          </div>

          {/* Card grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sortedEvents.map(event => (
              <Link 
                key={event.id} 
                to={`/events/${event.id}`}
                className="group block"
              >
                <Card className="overflow-hidden hover:border-primary/50 transition-colors">
                  <div className="relative aspect-[16/10] overflow-hidden">
                    <img 
                      src={event.cover_image_url} 
                      alt="" 
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" 
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
                    
                    <div className="absolute top-3 left-3">
                      <EventTypeBadge type={event.event_type} />
                    </div>
                    
                    <div className="absolute bottom-0 left-0 right-0 p-4 text-white">
                      <h3 className="font-semibold text-lg leading-tight group-hover:text-primary transition-colors">
                        {event.title}
                      </h3>
                      <p className="text-white/70 text-sm mt-1">
                        {formatDateRange(event.start_date, event.end_date)}
                      </p>
                    </div>
                  </div>
                  
                  <CardContent className="py-3 px-4">
                    <div className="flex justify-between text-sm text-muted-foreground">
                      <span>{event.total_distance_km} km</span>
                      <span>{event.total_elevation_m.toLocaleString()} m</span>
                      <span>{event.total_activities} {event.total_activities === 1 ? 'ride' : 'rides'}</span>
                      <span>{event.total_photos} photos</span>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
          
          {sortedEvents.length === 0 && filter !== "all" && (
            <div className="text-center py-12 text-muted-foreground">
              No {filter} events found.
            </div>
          )}
        </>
      )}

      {/* Prototype toggle for empty state testing */}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-card border border-border rounded-lg shadow-lg p-2 flex gap-2 z-50">
        <button
          onClick={() => setShowEmpty(false)}
          className={cn(
            "px-3 py-1.5 rounded text-sm font-medium transition-colors",
            !showEmpty ? "bg-emerald-600 text-white" : "hover:bg-muted"
          )}
        >
          With Events
        </button>
        <button
          onClick={() => setShowEmpty(true)}
          className={cn(
            "px-3 py-1.5 rounded text-sm font-medium transition-colors",
            showEmpty ? "bg-amber-600 text-white" : "hover:bg-muted"
          )}
        >
          Empty State
        </button>
      </div>
    </div>
  );
}
