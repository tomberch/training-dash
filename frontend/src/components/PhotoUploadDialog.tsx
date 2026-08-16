/**
 * Photo Upload Dialog
 * 
 * Dialog for batch uploading photos to an event.
 * Supports drag-and-drop and file picker with preview.
 */

import { useState, useRef, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { uploadEventPhotosBatch } from "@/api/events";
import { toast } from "sonner";

interface PhotoUploadDialogProps {
  eventId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded?: () => void;
}

interface FilePreview {
  file: File;
  previewUrl: string;
}

export function PhotoUploadDialog({
  eventId,
  open,
  onOpenChange,
  onUploaded,
}: PhotoUploadDialogProps) {
  const [files, setFiles] = useState<FilePreview[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const validFiles = Array.from(newFiles).filter((f) =>
      f.type.startsWith("image/")
    );
    
    if (validFiles.length === 0) {
      toast.error("Please select image files only");
      return;
    }

    const newPreviews = validFiles.map((file) => ({
      file,
      previewUrl: URL.createObjectURL(file),
    }));

    setFiles((prev) => [...prev, ...newPreviews]);
  }, []);

  const removeFile = (index: number) => {
    setFiles((prev) => {
      const updated = [...prev];
      URL.revokeObjectURL(updated[index].previewUrl);
      updated.splice(index, 1);
      return updated;
    });
  };

  const clearFiles = () => {
    files.forEach((f) => URL.revokeObjectURL(f.previewUrl));
    setFiles([]);
  };

  const handleClose = (open: boolean) => {
    if (!open) {
      clearFiles();
    }
    onOpenChange(open);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      const result = await uploadEventPhotosBatch(
        eventId,
        files.map((f) => f.file)
      );
      
      if (result.errors.length > 0) {
        toast.warning(
          `Uploaded ${result.count} photos, ${result.errors.length} failed`
        );
      } else {
        toast.success(`Uploaded ${result.count} ${result.count === 1 ? "photo" : "photos"}`);
      }
      
      handleClose(false);
      onUploaded?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to upload photos");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Upload Photos</DialogTitle>
          <DialogDescription>
            Add photos to this event. Drag and drop or click to select.
          </DialogDescription>
        </DialogHeader>

        {/* Drop zone */}
        <div
          className={cn(
            "border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer",
            isDragOver
              ? "border-primary bg-primary/10"
              : "border-border hover:border-muted-foreground"
          )}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
          <svg
            className="w-10 h-10 mx-auto text-muted-foreground mb-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          <p className="text-sm text-muted-foreground">
            Drop images here or click to browse
          </p>
        </div>

        {/* Preview grid */}
        {files.length > 0 && (
          <div className="max-h-[200px] overflow-y-auto">
            <div className="grid grid-cols-4 gap-2">
              {files.map((f, i) => (
                <div key={i} className="relative group aspect-square">
                  <img
                    src={f.previewUrl}
                    alt={f.file.name}
                    className="w-full h-full object-cover rounded-lg"
                  />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(i);
                    }}
                    className="absolute top-1 right-1 p-1 bg-black/60 text-white rounded opacity-0 group-hover:opacity-100 hover:bg-destructive transition-all"
                    title="Remove"
                  >
                    <svg
                      className="w-3 h-3"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={isUploading}
          >
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={isUploading || files.length === 0}>
            {isUploading
              ? "Uploading..."
              : files.length > 0
              ? `Upload ${files.length} ${files.length === 1 ? "Photo" : "Photos"}`
              : "Upload Photos"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
