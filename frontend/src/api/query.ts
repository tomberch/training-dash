/**
 * Query DSL and Saved Filters API
 */

import { API_BASE, ApiError, extractError, apiGet, apiPost, apiDelete } from "./base";

// ============================================================================
// Query DSL Types
// ============================================================================

export interface QueryErrorDetail {
  stage: "parse" | "validation" | "translation" | "execution";
  message: string;
  line?: number;
  column?: number;
  field?: string;
  suggestions?: string[];
  context?: string;
}

export interface ListQueryResponse {
  type: "list";
  results: Record<string, unknown>[];
  total: number;
  page: number;
  per_page: number;
}

export interface ScalarQueryResponse {
  type: "scalar";
  results: Record<string, unknown>;
}

export interface GroupedQueryResponse {
  type: "grouped";
  group_by: string[];
  results: Record<string, unknown>[];
}

export type QueryResponse = ListQueryResponse | ScalarQueryResponse | GroupedQueryResponse;

/**
 * Query-specific error with detailed stage information.
 */
export class QueryError extends Error {
  detail: QueryErrorDetail;

  constructor(detail: QueryErrorDetail) {
    super(detail.message);
    this.name = "QueryError";
    this.detail = detail;
  }
}

/**
 * Execute a query DSL string.
 */
export async function executeQuery(
  query: string,
  page: number = 1,
  perPage: number = 20
): Promise<QueryResponse> {
  const params = new URLSearchParams();
  params.set("page", page.toString());
  params.set("per_page", perPage.toString());

  const res = await fetch(`${API_BASE}/query?${params}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // FastAPI wraps HTTPException detail, so error is in body.detail.error
    const errorDetail = body.detail?.error || body.error;
    if (errorDetail) {
      throw new QueryError(errorDetail);
    }
    const { detail, errorId } = await extractError(res, "Query failed");
    throw new ApiError(detail, res.status, errorId);
  }

  return res.json();
}

// ============================================================================
// Saved Filters Types
// ============================================================================

export interface SavedFilter {
  id: number;
  name: string;
  query_text: string;
  description: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface SavedFilterListResponse {
  filters: SavedFilter[];
}

export interface CreateSavedFilterRequest {
  name: string;
  query_text: string;
  description?: string | null;
  is_default?: boolean;
}

export interface UpdateSavedFilterRequest {
  name?: string;
  query_text?: string;
  description?: string | null;
  is_default?: boolean;
}

// ============================================================================
// Saved Filters API
// ============================================================================

export async function fetchSavedFilters(): Promise<SavedFilter[]> {
  const response = await apiGet<SavedFilterListResponse>("/saved-filters");
  return response.filters;
}

export async function fetchDefaultFilter(): Promise<SavedFilter | null> {
  return apiGet<SavedFilter | null>("/saved-filters/default");
}

export async function fetchSavedFilter(id: number): Promise<SavedFilter> {
  return apiGet<SavedFilter>(`/saved-filters/${id}`);
}

export async function createSavedFilter(request: CreateSavedFilterRequest): Promise<SavedFilter> {
  const res = await fetch(`${API_BASE}/saved-filters`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    if (body.error) {
      throw new QueryError(body.error);
    }
    if (res.status === 409) {
      throw new ApiError(body.detail || "Filter with this name already exists", 409);
    }
    const { detail, errorId } = await extractError(res, "Failed to create filter");
    throw new ApiError(detail, res.status, errorId);
  }

  return res.json();
}

export async function updateSavedFilter(
  id: number,
  request: UpdateSavedFilterRequest
): Promise<SavedFilter> {
  const res = await fetch(`${API_BASE}/saved-filters/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    if (body.error) {
      throw new QueryError(body.error);
    }
    if (res.status === 409) {
      throw new ApiError(body.detail || "Filter with this name already exists", 409);
    }
    const { detail, errorId } = await extractError(res, "Failed to update filter");
    throw new ApiError(detail, res.status, errorId);
  }

  return res.json();
}

export async function deleteSavedFilter(id: number): Promise<void> {
  return apiDelete(`/saved-filters/${id}`, "Failed to delete filter");
}

export async function setDefaultFilter(id: number): Promise<SavedFilter> {
  return apiPost<SavedFilter>(
    `/saved-filters/${id}/set-default`,
    undefined,
    "Failed to set default filter"
  );
}

export async function clearDefaultFilter(): Promise<void> {
  return apiPost("/saved-filters/clear-default", undefined, "Failed to clear default filter");
}
