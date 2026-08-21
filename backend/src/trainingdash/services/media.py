"""
Media service for handling photo uploads, thumbnails, and file management.

This service encapsulates all file I/O operations for ride event media,
providing a clean interface for the router layer.
"""

import os
import shutil
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image

# Configuration constants
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10MB
THUMBNAIL_SIZE = (400, 400)  # Max dimensions for thumbnails
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class MediaValidationError(Exception):
    """Raised when media validation fails."""

    pass


@dataclass
class UploadedMedia:
    """Result of a successful media upload."""

    media_id: UUID
    storage_path: str
    thumbnail_path: str | None


@dataclass
class UploadResult:
    """Result of a batch upload operation."""

    uploaded: list[UploadedMedia]
    errors: list[dict]


class MediaService:
    """
    Service for managing ride event media files.

    Handles:
    - File validation (type, size)
    - Thumbnail generation
    - Safe path construction with traversal protection
    - File storage and deletion
    """

    def __init__(self, uploads_dir: Path | None = None):
        """
        Initialize the media service.

        Args:
            uploads_dir: Base directory for uploads. Defaults to TRAININGDASH_UPLOADS_DIR
                        environment variable or /app/uploads.
        """
        if uploads_dir is None:
            uploads_dir = Path(os.environ.get("TRAININGDASH_UPLOADS_DIR", "/app/uploads"))
        self._uploads_dir = uploads_dir

    @property
    def uploads_dir(self) -> Path:
        """Get the base uploads directory."""
        return self._uploads_dir

    def validate_image(self, content_type: str, size: int) -> None:
        """
        Validate an image before upload.

        Args:
            content_type: MIME type of the image
            size: Size in bytes

        Raises:
            MediaValidationError: If validation fails
        """
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise MediaValidationError(
                f"Unsupported image type: {content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"
            )
        if size > MAX_PHOTO_SIZE:
            raise MediaValidationError(
                f"Image too large ({size // 1024 // 1024}MB). Maximum size: {MAX_PHOTO_SIZE // 1024 // 1024}MB"
            )

    def get_event_uploads_dir(self, event_id: UUID) -> Path:
        """
        Get uploads directory for an event with path traversal protection.

        Args:
            event_id: Event UUID

        Returns:
            Safe path to event uploads directory

        Raises:
            ValueError: If path validation fails (should never happen with valid UUID)
        """
        base_dir = self._uploads_dir / "events"
        event_id_str = str(event_id)
        target_dir = base_dir / event_id_str

        # Defense in depth: verify the resolved path stays within base
        resolved = target_dir.resolve()
        base_resolved = base_dir.resolve()

        try:
            resolved.relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"Invalid event ID: {event_id}")

        return target_dir

    def get_entry_uploads_dir(self, event_id: UUID) -> Path:
        """
        Get uploads directory for journal entry files with path traversal protection.

        Args:
            event_id: Event UUID

        Returns:
            Safe path to entry uploads directory
        """
        event_dir = self.get_event_uploads_dir(event_id)
        return event_dir / "entries"

    def generate_thumbnail(self, image_bytes: bytes, content_type: str) -> bytes:
        """
        Generate a thumbnail from image bytes.

        Args:
            image_bytes: Raw image data
            content_type: MIME type of the image

        Returns:
            Thumbnail image bytes
        """
        img = Image.open(BytesIO(image_bytes))

        # Convert RGBA to RGB for JPEG output
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize maintaining aspect ratio
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        # Save to bytes
        output = BytesIO()
        format_map = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
            "image/gif": "GIF",
        }
        img_format = format_map.get(content_type, "JPEG")
        img.save(output, format=img_format, quality=85, optimize=True)
        return output.getvalue()

    def save_photo(
        self,
        image_bytes: bytes,
        content_type: str,
        event_id: UUID,
        *,
        is_entry: bool = False,
    ) -> UploadedMedia:
        """
        Save a photo and generate its thumbnail.

        Args:
            image_bytes: Raw image data
            content_type: MIME type of the image
            event_id: Event UUID for path construction
            is_entry: If True, save to entries subdirectory

        Returns:
            UploadedMedia with paths

        Raises:
            MediaValidationError: If validation fails
        """
        self.validate_image(content_type, len(image_bytes))

        media_id = uuid4()
        ext = IMAGE_EXTENSIONS.get(content_type, ".jpg")
        filename = f"{media_id}{ext}"
        thumb_filename = f"{media_id}_thumb{ext}"

        # Get appropriate directory
        if is_entry:
            uploads_dir = self.get_entry_uploads_dir(event_id)
            path_prefix = f"/uploads/events/{event_id}/entries"
        else:
            uploads_dir = self.get_event_uploads_dir(event_id)
            path_prefix = f"/uploads/events/{event_id}"

        # Ensure directory exists
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # Save original image
        filepath = uploads_dir / filename
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        # Generate and save thumbnail
        thumbnail_path = None
        try:
            thumbnail_bytes = self.generate_thumbnail(image_bytes, content_type)
            thumb_filepath = uploads_dir / thumb_filename
            with open(thumb_filepath, "wb") as f:
                f.write(thumbnail_bytes)
            thumbnail_path = f"{path_prefix}/{thumb_filename}"
        except Exception:  # noqa: S110
            # Failed to generate thumbnail, continue without - this is intentional
            # as we'd rather save the photo without a thumbnail than fail the upload
            pass

        return UploadedMedia(
            media_id=media_id,
            storage_path=f"{path_prefix}/{filename}",
            thumbnail_path=thumbnail_path,
        )

    def save_photos_batch(
        self,
        files: list[tuple[bytes, str, str | None]],  # (data, content_type, filename)
        event_id: UUID,
        *,
        is_entry: bool = False,
    ) -> UploadResult:
        """
        Save multiple photos in a batch.

        Args:
            files: List of (image_bytes, content_type, original_filename) tuples
            event_id: Event UUID
            is_entry: If True, save to entries subdirectory

        Returns:
            UploadResult with successful uploads and errors
        """
        uploaded: list[UploadedMedia] = []
        errors: list[dict] = []

        for image_bytes, content_type, filename in files:
            try:
                result = self.save_photo(image_bytes, content_type, event_id, is_entry=is_entry)
                uploaded.append(result)
            except MediaValidationError as e:
                errors.append({"filename": filename or "unknown", "error": str(e)})

        return UploadResult(uploaded=uploaded, errors=errors)

    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            storage_path: Path relative to uploads (e.g., /uploads/events/...)

        Returns:
            True if file was deleted, False if not found
        """
        # Convert storage path to filesystem path
        filepath = self._uploads_dir.parent / storage_path.lstrip("/")
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def delete_media_files(self, storage_path: str | None, thumbnail_path: str | None) -> None:
        """
        Delete both the main file and thumbnail for a media item.

        Args:
            storage_path: Main file path
            thumbnail_path: Thumbnail file path
        """
        if storage_path:
            self.delete_file(storage_path)
        if thumbnail_path:
            self.delete_file(thumbnail_path)

    def delete_event_directory(self, event_id: UUID) -> bool:
        """
        Delete the entire uploads directory for an event.

        Args:
            event_id: Event UUID

        Returns:
            True if directory was deleted, False if not found
        """
        uploads_dir = self.get_event_uploads_dir(event_id)
        if uploads_dir.exists():
            shutil.rmtree(uploads_dir, ignore_errors=True)
            return True
        return False


# Default instance for dependency injection
def get_media_service() -> MediaService:
    """Create a MediaService instance."""
    return MediaService()
