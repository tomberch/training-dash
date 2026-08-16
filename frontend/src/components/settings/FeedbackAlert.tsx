import { cn } from "@/lib/utils";

interface FeedbackAlertProps {
  feedback: { type: "success" | "error"; message: string } | null;
}

export function FeedbackAlert({ feedback }: FeedbackAlertProps) {
  if (!feedback) return null;
  return (
    <div
      className={cn(
        "mt-4 p-3 rounded-lg text-sm border",
        feedback.type === "success"
          ? "bg-success/10 text-success border-success/20"
          : "bg-destructive/10 text-destructive border-destructive/20"
      )}
    >
      {feedback.message}
    </div>
  );
}
