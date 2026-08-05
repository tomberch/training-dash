import { ApiError } from "./api";

interface ErrorDisplayProps {
  error: Error | ApiError | string;
  context?: string; // e.g., "loading activities", "uploading file"
}

/**
 * Displays an error message with optional error ID for debugging.
 * 
 * For ApiError instances, shows the error ID if present.
 * For generic errors, shows the message.
 * For strings, displays directly.
 */
export function ErrorDisplay({ error, context }: ErrorDisplayProps) {
  let message: string;
  let errorId: string | undefined;

  if (typeof error === "string") {
    message = error;
  } else if (error instanceof ApiError) {
    message = error.message;
    errorId = error.errorId;
  } else {
    message = error.message;
  }

  // Add context prefix if provided
  const displayMessage = context
    ? `Error ${context}: ${message}`
    : message;

  return (
    <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg">
      <p className="text-destructive">{displayMessage}</p>
      {errorId && (
        <p className="mt-2 text-xs text-destructive/80">
          Error ID: <code className="font-mono bg-destructive/20 px-1 py-0.5 rounded">{errorId}</code>
        </p>
      )}
    </div>
  );
}

/**
 * Helper to extract error info from a caught exception.
 * Returns a consistent shape for use with ErrorDisplay.
 */
export function getErrorInfo(error: unknown): { message: string; errorId?: string } {
  if (error instanceof ApiError) {
    return { message: error.message, errorId: error.errorId };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: String(error) };
}
