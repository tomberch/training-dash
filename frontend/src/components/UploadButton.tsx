import type { JSX } from "react";
import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { uploadFit, fetchJobStatus } from "../api";
import { Button } from "@/components/ui/button";
import { notifySuccess, notifyError } from "@/lib/notify";

interface UploadButtonProps {
  onUploadComplete?: () => void;
  onUploadTriggerRef?: (trigger: () => void) => void;
  className?: string;
}

/**
 * Reusable FIT file upload button with job polling and toast notifications.
 * Used in Header and Dashboard.
 */
export function UploadButton({
  onUploadComplete,
  onUploadTriggerRef,
  className,
}: UploadButtonProps): JSX.Element {
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Expose the upload trigger function to parent
  useEffect(() => {
    if (onUploadTriggerRef) {
      onUploadTriggerRef(() => fileInputRef.current?.click());
    }
  }, [onUploadTriggerRef]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadFit(file);
      let activityId: string | null | undefined;

      if ("job_id" in result && result.job_id) {
        setProcessing(true);
        const jobId = result.job_id;
        const maxPolls = 30;
        for (let i = 0; i < maxPolls; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          try {
            const status = await fetchJobStatus(jobId);
            if (status.status === "complete") {
              activityId = status.result?.activity_id;
              break;
            }
            if (status.status === "not_found") {
              break;
            }
          } catch {
            // Error checking status, keep polling
          }
        }
        setProcessing(false);
      } else if ("activity_id" in result) {
        activityId = result.activity_id as string;
      }

      onUploadComplete?.();

      // Show success toast with action to view activity
      if (activityId) {
        toast.success("Activity uploaded successfully", {
          action: {
            label: "View",
            onClick: () => navigate(`/activities/${activityId}`),
          },
        });
        // Also persist to bell (without the action button)
        notifySuccess("Activity uploaded", {
          bellType: "activity_uploaded",
          toastOnly: true, // Toast already shown above with action
        });
      } else {
        notifySuccess("Activity uploaded", {
          bellType: "activity_uploaded",
        });
      }
    } catch (err) {
      console.error("Upload failed:", err);
      notifyError("Upload failed", {
        description: err instanceof Error ? err.message : "Please try again",
        bellType: "activity_upload_failed",
      });
    } finally {
      setUploading(false);
      // Reset the input so the same file can be uploaded again
      e.target.value = "";
    }
  }

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept=".fit"
        onChange={handleUpload}
        disabled={uploading || processing}
        className="sr-only"
      />
      <Button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading || processing}
        className={className}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
          />
        </svg>
        {uploading ? "Uploading..." : processing ? "Processing..." : "Upload FIT"}
      </Button>
    </>
  );
}
