/**
 * Events API - CRUD operations for ride events, journal entries, media, and links
 */
import { apiGet, apiPost, apiPatch, apiDelete, API_BASE, ApiError, extractError } from "./base";

// Types
export interface RideEvent {
  id: string;
  title: string;
  event_type: string;
  start_date: string;
  end_date: string | null;
  description: string | null;
  cover_image_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface JournalEntry {
  id: string;
  ride_event_id: string;
  entry_date: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  media?: EventMedia[];
  links?: EventLink[];
  activities?: JournalEntryActivity[];
}

export interface EventMedia {
  id: string;
  ride_event_id: string | null;
  journal_entry_id: string | null;
  media_type: "photo" | "video";
  storage_path: string;
  thumbnail_path: string | null;
  caption: string | null;
  sort_order: number;
}

export interface EventLink {
  id: string;
  ride_event_id: string | null;
  journal_entry_id: string | null;
  url: string;
  title: string;
  link_type: string;
  sort_order: number;
}

export interface ActivityDetails {
  id: string;
  title: string | null;
  started_at: string | null;
  distance_km: number | null;
  elevation_m: number | null;
  duration_seconds: number | null;
  map_polyline: string | null;
}

export interface JournalEntryActivity {
  id: number;
  journal_entry_id: string;
  activity_id: string;
  sort_order: number;
  activity?: ActivityDetails;
}

export interface EventStats {
  total_distance_km: number | null;
  total_duration_seconds: number | null;
  total_elevation_m: number | null;
  total_tss: number | null;
  activity_count: number;
}

export interface EventDetail extends RideEvent {
  entries: (JournalEntry & {
    media: EventMedia[];
    links: EventLink[];
    activities: JournalEntryActivity[];
  })[];
  media: EventMedia[];
  links: EventLink[];
  stats: EventStats;
}

export interface PaginatedEvents {
  events: RideEvent[];
  pagination: {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
  };
}

export interface CreateEventRequest {
  title: string;
  event_type: string;
  start_date: string;
  end_date?: string;
  description?: string;
}

export interface UpdateEventRequest {
  title?: string;
  event_type?: string;
  start_date?: string;
  end_date?: string;
  description?: string;
}

export interface CreateJournalEntryRequest {
  entry_date: string;
  description?: string;
}

export interface UpdateJournalEntryRequest {
  entry_date?: string;
  description?: string;
}

export interface CreateLinkRequest {
  url: string;
  title: string;
  link_type?: string;
  sort_order?: number;
}

export interface CreateVideoRequest {
  url: string;
  title: string;
  sort_order?: number;
}

export interface AvailableActivity {
  id: string;
  title: string | null;
  started_at: string | null;
  distance_km: number | null;
  duration_seconds: number | null;
  is_linked: boolean;
}

export interface PaginatedActivities {
  activities: AvailableActivity[];
  pagination: {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
  };
}

// API Functions

// Events CRUD
export async function fetchEvents(
  page?: number,
  perPage?: number,
  eventType?: string
): Promise<PaginatedEvents> {
  const params = new URLSearchParams();
  if (page) params.set("page", page.toString());
  if (perPage) params.set("per_page", perPage.toString());
  if (eventType) params.set("event_type", eventType);
  const query = params.toString();
  return apiGet<PaginatedEvents>(`/events${query ? `?${query}` : ""}`);
}

export async function fetchEvent(id: string): Promise<EventDetail> {
  return apiGet<EventDetail>(`/events/${id}`);
}

export async function createEvent(data: CreateEventRequest): Promise<RideEvent> {
  return apiPost<RideEvent>("/events", data, "Failed to create event");
}

export async function updateEvent(id: string, data: UpdateEventRequest): Promise<RideEvent> {
  return apiPatch<RideEvent>(`/events/${id}`, data, "Failed to update event");
}

export async function deleteEvent(id: string): Promise<void> {
  return apiDelete(`/events/${id}`, "Failed to delete event");
}

// Journal Entries
export async function createJournalEntry(
  eventId: string,
  data: CreateJournalEntryRequest
): Promise<JournalEntry> {
  return apiPost<JournalEntry>(`/events/${eventId}/entries`, data, "Failed to create journal entry");
}

export async function updateJournalEntry(
  entryId: string,
  data: UpdateJournalEntryRequest
): Promise<JournalEntry> {
  return apiPatch<JournalEntry>(`/events/entries/${entryId}`, data, "Failed to update journal entry");
}

export async function deleteJournalEntry(entryId: string): Promise<void> {
  return apiDelete(`/events/entries/${entryId}`, "Failed to delete journal entry");
}

// Links
export async function createEventLink(eventId: string, data: CreateLinkRequest): Promise<EventLink> {
  return apiPost<EventLink>(`/events/${eventId}/links`, data, "Failed to add link");
}

export async function createEntryLink(entryId: string, data: CreateLinkRequest): Promise<EventLink> {
  return apiPost<EventLink>(`/events/entries/${entryId}/links`, data, "Failed to add link");
}

export async function deleteLink(linkId: string): Promise<void> {
  return apiDelete(`/events/links/${linkId}`, "Failed to delete link");
}

// Videos
export async function createEventVideo(eventId: string, data: CreateVideoRequest): Promise<EventMedia> {
  return apiPost<EventMedia>(`/events/${eventId}/videos`, data, "Failed to add video");
}

export async function createEntryVideo(entryId: string, data: CreateVideoRequest): Promise<EventMedia> {
  return apiPost<EventMedia>(`/events/entries/${entryId}/videos`, data, "Failed to add video");
}

export async function deleteEventVideo(eventId: string, videoId: string): Promise<void> {
  return apiDelete(`/events/${eventId}/videos/${videoId}`, "Failed to delete video");
}

export async function deleteEntryVideo(entryId: string, videoId: string): Promise<void> {
  return apiDelete(`/events/entries/${entryId}/videos/${videoId}`, "Failed to delete video");
}

// Photos
export async function uploadEventPhoto(
  eventId: string,
  file: File,
  caption?: string
): Promise<EventMedia> {
  const params = new URLSearchParams();
  if (caption) params.set("caption", caption);
  const query = params.toString();
  
  const res = await fetch(`${API_BASE}/events/${eventId}/photos${query ? `?${query}` : ""}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": file.type },
    body: file,
  });
  
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, "Failed to upload photo");
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function uploadEntryPhoto(
  entryId: string,
  file: File,
  caption?: string
): Promise<EventMedia> {
  const params = new URLSearchParams();
  if (caption) params.set("caption", caption);
  const query = params.toString();
  
  const res = await fetch(`${API_BASE}/events/entries/${entryId}/photos${query ? `?${query}` : ""}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": file.type },
    body: file,
  });
  
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, "Failed to upload photo");
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function uploadEventPhotosBatch(
  eventId: string,
  files: File[]
): Promise<{ uploaded: EventMedia[]; errors: { filename: string; error: string }[]; count: number }> {
  const formData = new FormData();
  files.forEach(file => formData.append("files", file));
  
  const res = await fetch(`${API_BASE}/events/${eventId}/photos/batch`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, "Failed to upload photos");
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function deleteMedia(mediaId: string): Promise<void> {
  return apiDelete(`/events/media/${mediaId}`, "Failed to delete media");
}

// Cover photo
export async function setEventCover(eventId: string, mediaId: string): Promise<RideEvent> {
  return apiPost<RideEvent>(`/events/${eventId}/cover/${mediaId}`, undefined, "Failed to set cover");
}

export async function removeEventCover(eventId: string): Promise<void> {
  return apiDelete(`/events/${eventId}/cover`, "Failed to remove cover");
}

// Activity linking
export async function fetchAvailableActivities(
  eventId: string,
  page?: number,
  perPage?: number
): Promise<PaginatedActivities> {
  const params = new URLSearchParams();
  if (page) params.set("page", page.toString());
  if (perPage) params.set("per_page", perPage.toString());
  const query = params.toString();
  return apiGet<PaginatedActivities>(`/events/${eventId}/available-activities${query ? `?${query}` : ""}`);
}

export async function batchLinkActivities(
  eventId: string,
  activityIds: string[]
): Promise<{ linked: JournalEntryActivity[]; count: number }> {
  return apiPost(`/events/${eventId}/activities`, { activity_ids: activityIds }, "Failed to link activities");
}

export async function unlinkActivityFromEvent(eventId: string, activityId: string): Promise<void> {
  return apiDelete(`/events/${eventId}/activities/${activityId}`, "Failed to unlink activity");
}

export async function linkActivityToEntry(
  entryId: string,
  activityId: string,
  sortOrder?: number
): Promise<JournalEntryActivity> {
  return apiPost(`/events/entries/${entryId}/activities`, {
    activity_id: activityId,
    sort_order: sortOrder ?? 0,
  }, "Failed to link activity");
}

export async function unlinkActivityFromEntry(entryId: string, activityId: string): Promise<void> {
  return apiDelete(`/events/entries/${entryId}/activities/${activityId}`, "Failed to unlink activity");
}

// Quick-link from activity page
export interface AvailableEvent {
  id: string;
  title: string;
  event_type: string;
  start_date: string;
  end_date: string | null;
}

export async function fetchAvailableEventsForActivity(activityId: string): Promise<{ events: AvailableEvent[] }> {
  return apiGet(`/activities/${activityId}/available-events`);
}

export async function quickLinkActivityToEvent(
  activityId: string,
  eventId: string
): Promise<{ event_id: string; entry_id: string; activity_id: string }> {
  return apiPost(`/activities/${activityId}/event`, { event_id: eventId }, "Failed to link activity to event");
}
