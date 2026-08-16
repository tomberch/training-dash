/**
 * Event Form Page
 * 
 * Create or edit a ride event.
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { fetchEvent, createEvent, updateEvent } from "@/api/events";
import type { EventDetail, CreateEventRequest, UpdateEventRequest } from "@/api/events";
import { cn } from "@/lib/utils";
import MDEditor from "@uiw/react-md-editor";
import rehypeSanitize from "rehype-sanitize";

const EVENT_TYPES = [
  { value: "race", label: "Race" },
  { value: "tour", label: "Tour" },
  { value: "bikepacking", label: "Bikepacking" },
  { value: "event", label: "Event" },
];

function BackIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
    </svg>
  );
}

export function EventFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditing = !!id && id !== "new";

  const [title, setTitle] = useState("");
  const [eventType, setEventType] = useState("event");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(isEditing);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load existing event if editing
  useEffect(() => {
    if (!isEditing || !id) return;
    setIsLoading(true);
    fetchEvent(id)
      .then((existingEvent: EventDetail) => {
        setTitle(existingEvent.title);
        setEventType(existingEvent.event_type);
        setStartDate(existingEvent.start_date);
        setEndDate(existingEvent.end_date || existingEvent.start_date);
        setDescription(existingEvent.description || "");
      })
      .catch((err: Error) => {
        toast.error("Failed to load event: " + err.message);
        navigate("/events");
      })
      .finally(() => setIsLoading(false));
  }, [id, isEditing, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!title.trim()) {
      toast.error("Title is required");
      return;
    }
    if (!startDate) {
      toast.error("Start date is required");
      return;
    }
    if (!endDate) {
      toast.error("End date is required");
      return;
    }

    setIsSubmitting(true);
    const data = {
      title: title.trim(),
      event_type: eventType,
      start_date: startDate,
      end_date: endDate,
      description: description.trim() || undefined,
    };

    try {
      if (isEditing && id) {
        await updateEvent(id, data as UpdateEventRequest);
        toast.success("Event updated");
        navigate(`/events/${id}`);
      } else {
        const newEvent = await createEvent(data as CreateEventRequest);
        toast.success("Event created");
        navigate(`/events/${newEvent.id}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save event");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="max-w-2xl mx-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-muted rounded w-1/4"></div>
            <div className="h-64 bg-muted rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(isEditing ? `/events/${id}` : "/events")}>
            <BackIcon />
          </Button>
          <h1 className="text-page-title">{isEditing ? "Edit Event" : "Create Event"}</h1>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Event Details</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Title */}
              <div className="space-y-2">
                <Label htmlFor="title">Title *</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., Alps Bikepacking 2024"
                  required
                />
              </div>

              {/* Event Type */}
              <div className="space-y-2">
                <Label>Event Type</Label>
                <div className="flex flex-wrap gap-2">
                  {EVENT_TYPES.map((type) => (
                    <button
                      key={type.value}
                      type="button"
                      onClick={() => setEventType(type.value)}
                      className={cn(
                        "px-3 py-1.5 text-sm rounded-lg transition-colors border",
                        eventType === type.value
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-muted hover:bg-muted/80 border-border"
                      )}
                    >
                      {type.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Date Range */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="start-date">Start Date *</Label>
                  <Input
                    id="start-date"
                    type="date"
                    value={startDate}
                    onChange={(e) => {
                      setStartDate(e.target.value);
                      // Auto-set end date if not set or before start
                      if (!endDate || e.target.value > endDate) {
                        setEndDate(e.target.value);
                      }
                    }}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="end-date">End Date *</Label>
                  <Input
                    id="end-date"
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    min={startDate}
                    required
                  />
                  <p className="text-caption">Same as start date for single-day events</p>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label>Description</Label>
                <div data-color-mode="dark">
                  <MDEditor
                    value={description}
                    onChange={(val) => setDescription(val || "")}
                    preview="live"
                    height={300}
                    visibleDragbar={false}
                    textareaProps={{
                      placeholder: "Tell the story of your event... (supports Markdown)",
                    }}
                    previewOptions={{
                      rehypePlugins: [[rehypeSanitize]],
                    }}
                  />
                </div>
                <p className="text-caption">Supports Markdown: **bold**, *italic*, # headings, - lists</p>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t border-border">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate(isEditing ? `/events/${id}` : "/events")}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Saving..." : isEditing ? "Save Changes" : "Create Event"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
