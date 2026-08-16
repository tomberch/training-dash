/**
 * Event Edit Page
 * 
 * Mirrors the detail page layout but with inline editing enabled.
 * Supports: editing descriptions, adding/removing links, photos, journal entries, and activities.
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import {
  fetchEvent,
  updateEvent,
  createJournalEntry,
  updateJournalEntry,
  deleteJournalEntry,
  createEventLink,
  createEntryLink,
  deleteLink,
  deleteMedia,
  setEventCover,
  unlinkActivityFromEvent,
} from "@/api/events";
import type { EventDetail, EventMedia, EventLink, JournalEntryActivity } from "@/api/events";
import { ActivityPickerDialog } from "@/components/ActivityPickerDialog";
import { PhotoUploadDialog } from "@/components/PhotoUploadDialog";
import MDEditor from "@uiw/react-md-editor";
import rehypeSanitize from "rehype-sanitize";
import { formatEventDuration, isSingleDayEvent, formatEventHeaderDates } from "@/lib/event-utils";


// Icons
function PlusIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

function StarIcon({ filled }: { filled?: boolean }) {
  return (
    <svg className={cn("w-4 h-4", filled ? "fill-yellow-400 text-yellow-400" : "")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
    </svg>
  );
}

function LinkIcon({ type }: { type: string }) {
  const icons: Record<string, string> = {
    route: "M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7",
    place: "M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z",
    article: "M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z",
    other: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
  };
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icons[type] || icons.other} />
    </svg>
  );
}


// Event type badge
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

// Stat card for header
function StatCard({ label, value, unit }: { label: string; value: number | string; unit?: string }) {
  return (
    <div className="text-center">
      <div className="text-metric">{value}{unit && <span className="text-lg ml-0.5">{unit}</span>}</div>
      <div className="text-metric-label">{label}</div>
    </div>
  );
}

// Activity card with unlink button
function ActivityCard({ activity, onUnlink }: { activity: JournalEntryActivity; onUnlink: () => void }) {
  const details = activity.activity;
  const title = details?.title || "Untitled Activity";
  const stats: string[] = [];
  if (details?.distance_km) stats.push(`${details.distance_km} km`);
  if (details?.elevation_m) stats.push(`${details.elevation_m}m`);
  if (details?.duration_seconds) stats.push(formatEventDuration(details.duration_seconds));

  return (
    <div className="flex items-center gap-4 p-3 bg-muted/50 rounded-lg group">
      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
        <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{title}</div>
        <div className="text-caption">{stats.length > 0 ? stats.join(" · ") : "No details"}</div>
      </div>
      <button
        onClick={onUnlink}
        className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-all"
        title="Unlink activity"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}


// Photo gallery with delete and set-cover actions
function EditablePhotoGallery({ 
  photos, 
  coverId,
  onDelete, 
  onSetCover 
}: { 
  photos: EventMedia[]; 
  coverId: string | null;
  onDelete: (id: string) => void;
  onSetCover: (id: string) => void;
}) {
  if (photos.length === 0) return null;
  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {photos.map((media) => (
        <div key={media.id} className="relative group flex-shrink-0">
          <img
            src={media.thumbnail_path || media.storage_path}
            alt={media.caption || ""}
            className={cn(
              "w-24 h-24 object-cover rounded-lg",
              media.id === coverId && "ring-2 ring-yellow-400"
            )}
          />
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-1">
            <button
              onClick={() => onSetCover(media.id)}
              className={cn(
                "p-1.5 rounded transition-colors",
                media.id === coverId 
                  ? "bg-yellow-400 text-black" 
                  : "bg-white/20 text-white hover:bg-white/40"
              )}
              title={media.id === coverId ? "Current cover" : "Set as cover"}
            >
              <StarIcon filled={media.id === coverId} />
            </button>
            <button
              onClick={() => onDelete(media.id)}
              className="p-1.5 bg-white/20 text-white rounded hover:bg-destructive transition-colors"
              title="Delete photo"
            >
              <TrashIcon />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// Editable links list
function EditableLinksList({ 
  links, 
  onDelete 
}: { 
  links: EventLink[]; 
  onDelete: (id: string) => void;
}) {
  if (links.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {links.map((link) => (
        <div key={link.id} className="inline-flex items-center gap-1.5 px-2 py-1 bg-muted rounded text-sm group">
          <LinkIcon type={link.link_type} />
          <a href={link.url} target="_blank" rel="noopener noreferrer" className="hover:text-primary">
            {link.title}
          </a>
          <button
            onClick={() => onDelete(link.id)}
            className="ml-1 p-0.5 text-muted-foreground hover:text-destructive transition-colors"
            title="Remove link"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}


// Add Link Dialog
function AddLinkDialog({
  open,
  onOpenChange,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (url: string, title: string, linkType: string) => void;
}) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [linkType, setLinkType] = useState("other");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() || !title.trim()) return;
    onAdd(url.trim(), title.trim(), linkType);
    setUrl("");
    setTitle("");
    setLinkType("other");
    onOpenChange(false);
  };

  const linkTypes = [
    { value: "route", label: "Route" },
    { value: "place", label: "Place" },
    { value: "article", label: "Article" },
    { value: "gear", label: "Gear" },
    { value: "other", label: "Other" },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Link</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="link-url">URL *</Label>
            <Input
              id="link-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="link-title">Title *</Label>
            <Input
              id="link-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Link title"
              required
            />
          </div>
          <div className="space-y-2">
            <Label>Type</Label>
            <div className="flex flex-wrap gap-2">
              {linkTypes.map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setLinkType(type.value)}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-lg transition-colors border",
                    linkType === type.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-muted hover:bg-muted/80 border-border"
                  )}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit">Add Link</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}


// Add Journal Entry Dialog
function AddEntryDialog({
  open,
  onOpenChange,
  eventStartDate,
  eventEndDate,
  existingDates,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  eventStartDate: string;
  eventEndDate: string;
  existingDates: string[];
  onAdd: (date: string) => void;
}) {
  const [date, setDate] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!date) return;
    if (existingDates.includes(date)) {
      toast.error("An entry for this date already exists");
      return;
    }
    onAdd(date);
    setDate("");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Journal Entry</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="entry-date">Date *</Label>
            <Input
              id="entry-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              min={eventStartDate}
              max={eventEndDate}
              required
            />
            <p className="text-caption">Must be within the event date range</p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit">Add Entry</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}


// Main component
export function EventEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  
  // Edit state for event description
  const [eventDescription, setEventDescription] = useState("");
  const [hasDescriptionChanges, setHasDescriptionChanges] = useState(false);
  
  // Edit state for entry descriptions (keyed by entry ID)
  const [entryDescriptions, setEntryDescriptions] = useState<Record<string, string>>({});
  const [entryDescriptionChanges, setEntryDescriptionChanges] = useState<Record<string, boolean>>({});
  
  // Dialogs
  const [showActivityPicker, setShowActivityPicker] = useState(false);
  const [showPhotoUpload, setShowPhotoUpload] = useState(false);
  const [showAddEventLink, setShowAddEventLink] = useState(false);
  const [showAddEntryLink, setShowAddEntryLink] = useState<string | null>(null);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const [entryToDelete, setEntryToDelete] = useState<{ id: string; date: string } | null>(null);

  const loadEvent = () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchEvent(id)
      .then((data) => {
        setEvent(data);
        setEventDescription(data.description || "");
        // Initialize entry descriptions
        const descs: Record<string, string> = {};
        data.entries.forEach(e => { descs[e.id] = e.description || ""; });
        setEntryDescriptions(descs);
        setEntryDescriptionChanges({});
        setHasDescriptionChanges(false);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadEvent();
  }, [id]);


  // Save event description
  const handleSaveEventDescription = async () => {
    if (!id || !event) return;
    setIsSaving(true);
    try {
      await updateEvent(id, { description: eventDescription || undefined });
      setHasDescriptionChanges(false);
      toast.success("Description saved");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setIsSaving(false);
    }
  };

  // Save entry description
  const handleSaveEntryDescription = async (entryId: string) => {
    setIsSaving(true);
    try {
      await updateJournalEntry(entryId, { description: entryDescriptions[entryId] || undefined });
      setEntryDescriptionChanges(prev => ({ ...prev, [entryId]: false }));
      toast.success("Entry saved");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setIsSaving(false);
    }
  };

  // Add event link
  const handleAddEventLink = async (url: string, title: string, linkType: string) => {
    if (!id) return;
    try {
      await createEventLink(id, { url, title, link_type: linkType });
      toast.success("Link added");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add link");
    }
  };

  // Add entry link
  const handleAddEntryLink = async (entryId: string, url: string, title: string, linkType: string) => {
    try {
      await createEntryLink(entryId, { url, title, link_type: linkType });
      toast.success("Link added");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add link");
    }
  };

  // Delete link
  const handleDeleteLink = async (linkId: string) => {
    try {
      await deleteLink(linkId);
      toast.success("Link removed");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove link");
    }
  };


  // Delete photo
  const handleDeletePhoto = async (mediaId: string) => {
    try {
      await deleteMedia(mediaId);
      toast.success("Photo deleted");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete photo");
    }
  };

  // Set cover photo
  const handleSetCover = async (mediaId: string) => {
    if (!id) return;
    try {
      await setEventCover(id, mediaId);
      toast.success("Cover photo set");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to set cover");
    }
  };

  // Unlink activity
  const handleUnlinkActivity = async (activityId: string) => {
    if (!id) return;
    try {
      await unlinkActivityFromEvent(id, activityId);
      toast.success("Activity unlinked");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to unlink activity");
    }
  };

  // Add journal entry
  const handleAddEntry = async (date: string) => {
    if (!id) return;
    try {
      await createJournalEntry(id, { entry_date: date });
      toast.success("Entry added");
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add entry");
    }
  };

  // Delete journal entry
  const handleDeleteEntry = async () => {
    if (!entryToDelete) return;
    try {
      await deleteJournalEntry(entryToDelete.id);
      toast.success("Entry deleted");
      setEntryToDelete(null);
      loadEvent();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete entry");
    }
  };


  // Loading/error states
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
      <div className="-m-6">
        <Skeleton className="h-80 w-full" />
        <div className="p-6 space-y-4">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  const isSingleDay = isSingleDayEvent(event.start_date, event.end_date);
  const stats = event.stats;

  // Cover image
  const coverMedia = event.cover_image_id 
    ? event.media.find(m => m.id === event.cover_image_id) 
    : null;
  
  const gradients = [
    "from-blue-600 to-purple-600",
    "from-emerald-600 to-teal-600",
    "from-orange-600 to-red-600",
    "from-pink-600 to-rose-600",
    "from-indigo-600 to-blue-600",
  ];
  const gradientIndex = event.id.charCodeAt(0) % gradients.length;

  // All photos (event + entries)
  const allPhotos = [
    ...event.media.filter((m) => m.media_type === "photo"),
    ...event.entries.flatMap(e => e.media.filter((m) => m.media_type === "photo"))
  ];

  const existingEntryDates = event.entries.map(e => e.entry_date);


  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <button 
            onClick={() => navigate(`/events/${id}`)} 
            className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 hover:underline"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Done Editing
          </button>
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
          <EventTypeBadge type={event.event_type} />
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

      {/* Content */}
      <div className="space-y-8">
        {/* Event Description */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">Event Description</Label>
            {hasDescriptionChanges && (
              <Button size="sm" onClick={handleSaveEventDescription} disabled={isSaving}>
                {isSaving ? "Saving..." : "Save Description"}
              </Button>
            )}
          </div>
          <div data-color-mode="dark">
            <MDEditor
              value={eventDescription}
              onChange={(val) => {
                setEventDescription(val || "");
                setHasDescriptionChanges(true);
              }}
              preview="live"
              height={200}
              visibleDragbar={false}
              textareaProps={{ placeholder: "Describe your event... (supports Markdown)" }}
              previewOptions={{ rehypePlugins: [[rehypeSanitize]] }}
            />
          </div>
        </div>

        {/* Event Links */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">Event Links</Label>
            <Button variant="ghost" size="icon" onClick={() => setShowAddEventLink(true)} title="Add link">
              <PlusIcon />
            </Button>
          </div>
          {event.links.length > 0 ? (
            <EditableLinksList links={event.links} onDelete={handleDeleteLink} />
          ) : (
            <p className="text-muted-foreground text-sm">No links yet</p>
          )}
        </div>

        {/* Event Photos */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">Event Photos</Label>
            <Button variant="ghost" size="icon" onClick={() => setShowPhotoUpload(true)} title="Add photos">
              <PlusIcon />
            </Button>
          </div>
          {event.media.filter(m => m.media_type === "photo").length > 0 ? (
            <EditablePhotoGallery
              photos={event.media.filter(m => m.media_type === "photo")}
              coverId={event.cover_image_id}
              onDelete={handleDeletePhoto}
              onSetCover={handleSetCover}
            />
          ) : (
            <p className="text-muted-foreground text-sm">No photos yet. Add photos to set a cover image.</p>
          )}
        </div>


        {/* Journal Entries */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-card-title">{isSingleDay ? "Details" : "Day by Day"}</h2>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowActivityPicker(true)}>
                Link Activities
              </Button>
              {!isSingleDay && (
                <Button variant="outline" size="sm" onClick={() => setShowAddEntry(true)}>
                  Add Day
                </Button>
              )}
            </div>
          </div>

          {event.entries.length > 0 ? (
            event.entries.map((entry, i) => (
              <div 
                key={entry.id} 
                className={cn(
                  "space-y-4",
                  !isSingleDay && "relative pl-8 pb-6 border-l-2 border-border last:border-l-0 last:pb-0"
                )}
              >
                {/* Day marker (multi-day only) */}
                {!isSingleDay && (
                  <>
                    <div className="absolute left-0 top-0 -translate-x-1/2 w-4 h-4 rounded-full bg-primary border-4 border-background" />
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-muted-foreground">
                        Day {i + 1} · {new Date(entry.entry_date).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
                      </span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-muted-foreground hover:text-destructive"
                        onClick={() => setEntryToDelete({ id: entry.id, date: entry.entry_date })}
                      >
                        <TrashIcon />
                      </Button>
                    </div>
                  </>
                )}

                {/* Activities */}
                {entry.activities.length > 0 && (
                  <div className="space-y-2">
                    {entry.activities.map((a: JournalEntryActivity) => (
                      <ActivityCard key={a.id} activity={a} onUnlink={() => handleUnlinkActivity(a.activity_id)} />
                    ))}
                  </div>
                )}


                {/* Entry Description */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">Journal Entry</Label>
                    {entryDescriptionChanges[entry.id] && (
                      <Button size="sm" variant="outline" onClick={() => handleSaveEntryDescription(entry.id)} disabled={isSaving}>
                        Save
                      </Button>
                    )}
                  </div>
                  <div data-color-mode="dark">
                    <MDEditor
                      value={entryDescriptions[entry.id] || ""}
                      onChange={(val) => {
                        setEntryDescriptions(prev => ({ ...prev, [entry.id]: val || "" }));
                        setEntryDescriptionChanges(prev => ({ ...prev, [entry.id]: true }));
                      }}
                      preview="edit"
                      height={150}
                      visibleDragbar={false}
                      textareaProps={{ placeholder: "Write about this day..." }}
                      previewOptions={{ rehypePlugins: [[rehypeSanitize]] }}
                    />
                  </div>
                </div>

                {/* Entry Photos */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">Photos</Label>
                    <Button variant="ghost" size="sm" onClick={() => setShowPhotoUpload(true)} title="Add photos to event">
                      <PlusIcon />
                    </Button>
                  </div>
                  {entry.media.filter(m => m.media_type === "photo").length > 0 ? (
                    <EditablePhotoGallery
                      photos={entry.media.filter(m => m.media_type === "photo")}
                      coverId={event.cover_image_id}
                      onDelete={handleDeletePhoto}
                      onSetCover={handleSetCover}
                    />
                  ) : (
                    <p className="text-muted-foreground text-xs">No photos for this day</p>
                  )}
                </div>

                {/* Entry Links */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">Links</Label>
                    <Button variant="ghost" size="sm" onClick={() => setShowAddEntryLink(entry.id)}>
                      <PlusIcon />
                    </Button>
                  </div>
                  {entry.links.length > 0 ? (
                    <EditableLinksList links={entry.links} onDelete={handleDeleteLink} />
                  ) : (
                    <p className="text-muted-foreground text-xs">No links for this day</p>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-muted-foreground border border-dashed border-border rounded-lg">
              <p>No journal entries yet.</p>
              <p className="text-sm mt-1">Link activities to automatically create entries, or add a day manually.</p>
            </div>
          )}
        </div>
      </div>


      {/* Dialogs */}
      <ActivityPickerDialog
        eventId={id}
        open={showActivityPicker}
        onOpenChange={setShowActivityPicker}
        onLinked={loadEvent}
      />
      
      <PhotoUploadDialog
        eventId={id}
        open={showPhotoUpload}
        onOpenChange={setShowPhotoUpload}
        onUploaded={loadEvent}
      />

      <AddLinkDialog
        open={showAddEventLink}
        onOpenChange={setShowAddEventLink}
        onAdd={handleAddEventLink}
      />

      <AddLinkDialog
        open={!!showAddEntryLink}
        onOpenChange={(open) => !open && setShowAddEntryLink(null)}
        onAdd={(url, title, linkType) => {
          if (showAddEntryLink) {
            handleAddEntryLink(showAddEntryLink, url, title, linkType);
          }
        }}
      />

      <AddEntryDialog
        open={showAddEntry}
        onOpenChange={setShowAddEntry}
        eventStartDate={event.start_date}
        eventEndDate={event.end_date || event.start_date}
        existingDates={existingEntryDates}
        onAdd={handleAddEntry}
      />

      {/* Delete Entry Confirmation */}
      <AlertDialog open={!!entryToDelete} onOpenChange={(open) => !open && setEntryToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Journal Entry</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the entry for {entryToDelete?.date ? new Date(entryToDelete.date).toLocaleDateString() : ""}? 
              This will also delete all photos and links for this day. Activities will be unlinked but not deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteEntry} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
