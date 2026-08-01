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
    <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
      <p className="text-red-700 dark:text-red-400">{displayMessage}</p>
      {errorId && (
        <p className="mt-2 text-xs text-red-500 dark:text-red-500">
          Error ID: <code className="font-mono bg-red-100 dark:bg-red-900/40 px-1 py-0.5 rounded">{errorId}</code>
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
