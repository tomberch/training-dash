/**
 * API base helpers - error handling and HTTP request utilities
 */

export const API_BASE = import.meta.env.VITE_API_URL || "/api";

/**
 * Structured API error with optional error_id for tracking.
 */
export class ApiError extends Error {
  status: number;
  errorId?: string;

  constructor(message: string, status: number, errorId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorId = errorId;
  }
}

/**
 * Extract error details from a failed response.
 */
export async function extractError(
  res: Response,
  defaultMessage: string
): Promise<{ detail: string; errorId?: string }> {
  let detail = defaultMessage;
  let errorId: string | undefined;
  try {
    const body = await res.json();
    detail = body.detail || detail;
    errorId = body.error_id;
  } catch {
    detail = res.statusText || detail;
  }
  return { detail, errorId };
}

/**
 * GET request helper - fetches JSON from an API endpoint.
 */
export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, "Request failed");
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

/**
 * POST request helper - posts JSON to an API endpoint.
 */
export async function apiPost<T>(
  path: string,
  body?: unknown,
  errorMessage = "Request failed"
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, errorMessage);
    throw new ApiError(detail, res.status, errorId);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : ({} as T);
}

/**
 * PUT request helper - puts JSON to an API endpoint.
 */
export async function apiPut<T>(
  path: string,
  body: unknown,
  errorMessage = "Request failed"
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, errorMessage);
    throw new ApiError(detail, res.status, errorId);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : ({} as T);
}

/**
 * PATCH request helper - patches JSON to an API endpoint.
 */
export async function apiPatch<T>(
  path: string,
  body: unknown,
  errorMessage = "Request failed"
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, errorMessage);
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

/**
 * DELETE request helper.
 */
export async function apiDelete(path: string, errorMessage = "Request failed"): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, errorMessage);
    throw new ApiError(detail, res.status, errorId);
  }
}
