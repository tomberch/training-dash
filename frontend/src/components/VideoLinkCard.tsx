/**
 * VideoLinkCard - Renders a video link with thumbnail preview.
 * Supports YouTube and Vimeo URLs with automatic thumbnail extraction.
 */

import { useMemo } from "react";

interface VideoLinkCardProps {
  url: string;
  title: string;
}

/**
 * Extract video ID and provider from a YouTube or Vimeo URL.
 */
function parseVideoUrl(url: string): { provider: "youtube" | "vimeo" | null; videoId: string | null } {
  // YouTube patterns:
  // - https://www.youtube.com/watch?v=VIDEO_ID
  // - https://youtu.be/VIDEO_ID
  // - https://www.youtube.com/embed/VIDEO_ID
  // - https://www.youtube.com/v/VIDEO_ID
  const youtubePatterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})/,
  ];

  for (const pattern of youtubePatterns) {
    const match = url.match(pattern);
    if (match) {
      return { provider: "youtube", videoId: match[1] };
    }
  }

  // Vimeo patterns:
  // - https://vimeo.com/VIDEO_ID
  // - https://player.vimeo.com/video/VIDEO_ID
  const vimeoPatterns = [
    /vimeo\.com\/(\d+)/,
    /player\.vimeo\.com\/video\/(\d+)/,
  ];

  for (const pattern of vimeoPatterns) {
    const match = url.match(pattern);
    if (match) {
      return { provider: "vimeo", videoId: match[1] };
    }
  }

  return { provider: null, videoId: null };
}

/**
 * Get thumbnail URL for a video.
 */
function getThumbnailUrl(provider: "youtube" | "vimeo", videoId: string): string {
  if (provider === "youtube") {
    // mqdefault is 320x180, good balance of quality and size
    return `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`;
  }
  // Vimeo: use vumbnail.com free service
  return `https://vumbnail.com/${videoId}.jpg`;
}

export function VideoLinkCard({ url, title }: VideoLinkCardProps) {
  const { provider, videoId } = useMemo(() => parseVideoUrl(url), [url]);
  const thumbnailUrl = provider && videoId ? getThumbnailUrl(provider, videoId) : null;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block w-48 flex-shrink-0 rounded-lg overflow-hidden bg-muted hover:ring-2 hover:ring-primary/50 transition-all"
    >
      {/* Thumbnail with play overlay */}
      <div className="relative aspect-video bg-muted-foreground/20">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={title}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-10 h-10 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        )}
        {/* Play button overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center">
            <svg className="w-6 h-6 text-black ml-0.5" fill="currentColor" viewBox="0 0 24 24">
              <polygon points="8,5 19,12 8,19" />
            </svg>
          </div>
        </div>
      </div>
      {/* Title */}
      <div className="p-2">
        <p className="text-sm font-medium truncate">{title}</p>
        {provider && (
          <p className="text-xs text-muted-foreground capitalize">{provider}</p>
        )}
      </div>
    </a>
  );
}

/**
 * Check if a URL is a supported video URL.
 */
export function isVideoUrl(url: string): boolean {
  const { provider } = parseVideoUrl(url);
  return provider !== null;
}
