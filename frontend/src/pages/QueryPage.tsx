import type { JSX } from "react";
import { useState, useCallback, useRef, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  executeQuery,
  QueryError,
  type QueryResponse,
  type ListQueryResponse,
  type ScalarQueryResponse,
  type GroupedQueryResponse,
  type QueryErrorDetail,
} from "../api";
import { formatDistance, formatDuration, formatActivityDate } from "../format";

// === Icons ===

function PlayIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function LoadingIcon() {
  return (
    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}

// === Query Input ===

interface QueryInputProps {
  value: string;
  onChange: (value: string) => void;
  onExecute: () => void;
  loading: boolean;
  error: QueryErrorDetail | null;
}

function QueryInput({ value, onChange, onExecute, loading, error }: QueryInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.max(80, textarea.scrollHeight)}px`;
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Ctrl/Cmd + Enter to execute
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (!loading && value.trim()) {
        onExecute();
      }
    }
  };

  return (
    <div className="space-y-2">
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter query... e.g. tss > 100 AND date >= START_OF_MONTH"
          className={cn(
            "w-full px-4 py-3 font-mono text-sm rounded-lg border resize-none",
            "bg-background text-foreground placeholder:text-muted-foreground",
            "focus:outline-none focus:ring-2 focus:ring-primary/50",
            error ? "border-destructive" : "border-border"
          )}
          rows={2}
        />
      </div>

      <div className="flex items-center justify-between">
        <span className="text-caption">
          Press <kbd className="px-1.5 py-0.5 rounded bg-muted text-xs font-mono">Ctrl</kbd>+<kbd className="px-1.5 py-0.5 rounded bg-muted text-xs font-mono">Enter</kbd> to run
        </span>
        <Button
          onClick={onExecute}
          disabled={loading || !value.trim()}
          className="gap-2"
        >
          {loading ? <LoadingIcon /> : <PlayIcon />}
          {loading ? "Running..." : "Run Query"}
        </Button>
      </div>
    </div>
  );
}

// === Error Display ===

interface ErrorDisplayProps {
  error: QueryErrorDetail;
  query: string;
}

function ErrorDisplay({ error, query }: ErrorDisplayProps) {
  // Build context display if we have line/column info
  let contextDisplay: JSX.Element | null = null;

  if (error.context) {
    contextDisplay = (
      <pre className="mt-2 p-2 bg-background rounded text-xs font-mono overflow-x-auto">
        {error.context}
      </pre>
    );
  } else if (error.line && error.column && query) {
    const lines = query.split("\n");
    const errorLine = lines[error.line - 1] || "";
    const pointer = " ".repeat(Math.max(0, error.column - 1)) + "^";
    contextDisplay = (
      <pre className="mt-2 p-2 bg-background rounded text-xs font-mono overflow-x-auto">
        <code className="text-foreground">{errorLine}</code>
        {"\n"}
        <code className="text-destructive">{pointer}</code>
      </pre>
    );
  }

  return (
    <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20">
      <div className="flex items-start gap-3">
        <span className="text-destructive mt-0.5">
          <AlertIcon />
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-destructive">
              {error.stage.charAt(0).toUpperCase() + error.stage.slice(1)} Error
            </span>
            {error.line && error.column && (
              <span className="text-caption">
                at line {error.line}, column {error.column}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-foreground">{error.message}</p>
          {contextDisplay}
          {error.field && (
            <p className="mt-2 text-caption">
              Field: <code className="px-1 py-0.5 rounded bg-muted font-mono text-xs">{error.field}</code>
            </p>
          )}
          {error.suggestions && error.suggestions.length > 0 && (
            <div className="mt-2">
              <span className="text-caption">Did you mean: </span>
              {error.suggestions.map((s, i) => (
                <span key={s}>
                  <code className="px-1 py-0.5 rounded bg-muted font-mono text-xs">{s}</code>
                  {i < error.suggestions!.length - 1 && ", "}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// === Results Display ===

interface ListResultsProps {
  response: ListQueryResponse;
  page: number;
  onPageChange: (page: number) => void;
}

function ListResults({ response, page, onPageChange }: ListResultsProps) {
  const navigate = useNavigate();
  const { results, total, per_page } = response;
  const totalPages = Math.ceil(total / per_page);

  if (results.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No activities match your query
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results count */}
      <div className="text-body-secondary">
        Showing {results.length} of {total} activities
      </div>

      {/* Activity list */}
      <div className="space-y-2">
        {results.map((activity) => (
          <button
            type="button"
            key={activity.id as string}
            className="w-full text-left p-4 rounded-lg bg-card border border-border hover:bg-muted/50 cursor-pointer transition-colors"
            onClick={() => navigate(`/activities/${activity.id}`)}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h3 className="font-medium text-foreground truncate">
                  {(activity.title as string) || "Untitled Activity"}
                </h3>
                <p className="text-caption mt-1">
                  {formatActivityDate(activity.started_at as string)}
                </p>
              </div>
              <div className="flex gap-6 text-sm shrink-0">
                {activity.total_distance_m != null && (
                  <div className="text-right">
                    <div className="text-foreground font-medium">
                      {formatDistance(activity.total_distance_m as number, "metric")}
                    </div>
                    <div className="text-caption">Distance</div>
                  </div>
                )}
                {activity.moving_time_s != null && (
                  <div className="text-right">
                    <div className="text-foreground font-medium">
                      {formatDuration(activity.moving_time_s as number)}
                    </div>
                    <div className="text-caption">Time</div>
                  </div>
                )}
                {activity.tss != null && (
                  <div className="text-right">
                    <div className="text-foreground font-medium">
                      {Math.round(activity.tss as number)}
                    </div>
                    <div className="text-caption">TSS</div>
                  </div>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
          >
            <ChevronLeftIcon />
            Previous
          </Button>
          <span className="text-sm text-muted-foreground px-4">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
          >
            Next
            <ChevronRightIcon />
          </Button>
        </div>
      )}
    </div>
  );
}

interface ScalarResultsProps {
  response: ScalarQueryResponse;
}

function ScalarResults({ response }: ScalarResultsProps) {
  const { results } = response;
  const entries = Object.entries(results);

  if (entries.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No results
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {entries.map(([key, value]) => (
        <div key={key} className="p-4 rounded-lg bg-card border border-border">
          <div className="text-metric text-foreground">
            {typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value ?? "—")}
          </div>
          <div className="text-metric-label mt-1">{formatAggregateLabel(key)}</div>
        </div>
      ))}
    </div>
  );
}

interface GroupedResultsProps {
  response: GroupedQueryResponse;
}

function GroupedResults({ response }: GroupedResultsProps) {
  const { group_by, results } = response;

  if (results.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No results
      </div>
    );
  }

  // Get all column keys from first result
  const firstResult = results[0];
  const valueKeys = Object.keys(firstResult).filter((k) => !group_by.includes(k));

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border">
            {group_by.map((col) => (
              <th key={col} className="px-4 py-3 text-left text-section-heading">
                {formatGroupByLabel(col)}
              </th>
            ))}
            {valueKeys.map((col) => (
              <th key={col} className="px-4 py-3 text-right text-section-heading">
                {formatAggregateLabel(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0 hover:bg-muted/50">
              {group_by.map((col) => (
                <td key={col} className="px-4 py-3 text-foreground">
                  {formatGroupValue(col, row[col])}
                </td>
              ))}
              {valueKeys.map((col) => (
                <td key={col} className="px-4 py-3 text-right text-foreground tabular-nums">
                  {formatAggregateValue(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// === Formatting helpers ===

function formatAggregateLabel(key: string): string {
  // e.g. "count_star" -> "Count", "avg_tss" -> "Avg TSS"
  return key
    .replace(/_star$/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatGroupByLabel(key: string): string {
  // e.g. "time_bucket" -> "Period", field names stay as-is
  if (key === "time_bucket") return "Period";
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatGroupValue(key: string, value: unknown): string {
  if (value == null) return "—";
  if (key === "time_bucket" && typeof value === "string") {
    // Format ISO date as readable month/week
    const date = new Date(value);
    if (!isNaN(date.getTime())) {
      return date.toLocaleDateString(undefined, { year: "numeric", month: "short" });
    }
  }
  return String(value);
}

function formatAggregateValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number") {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(value);
}

// === Loading Skeleton ===

function ResultsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-5 w-48" />
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    </div>
  );
}

// === Main Page ===

export function QueryPage(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(() => searchParams.get("q") || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<QueryErrorDetail | null>(null);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [page, setPage] = useState(1);

  // Sync query from URL when it changes externally (e.g., browser navigation)
  useEffect(() => {
    const q = searchParams.get("q");
    if (q !== null && q !== query) {
      setQuery(q);
    }
  }, [searchParams, query]);

  const runQuery = useCallback(async (queryText: string, pageNum: number = 1) => {
    if (!queryText.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await executeQuery(queryText, pageNum, 20);
      setResponse(result);
      setPage(pageNum);
      // Update URL
      setSearchParams({ q: queryText }, { replace: true });
    } catch (err) {
      if (err instanceof QueryError) {
        setError(err.detail);
      } else {
        setError({
          stage: "execution",
          message: err instanceof Error ? err.message : "Unknown error",
        });
      }
      setResponse(null);
    } finally {
      setLoading(false);
    }
  }, [setSearchParams]);

  // Run initial query from URL
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !response && !loading) {
      runQuery(q);
    }
  }, []);

  const handleExecute = () => {
    runQuery(query, 1);
  };

  const handlePageChange = (newPage: number) => {
    runQuery(query, newPage);
  };

  return (
    <div className="p-6">
      <PageHeader
        title="Query"
        subtitle="Search and analyze activities with a powerful query language"
      />

      {/* Query input section */}
      <div className="mb-6">
        <QueryInput
          value={query}
          onChange={setQuery}
          onExecute={handleExecute}
          loading={loading}
          error={error}
        />
      </div>

      {/* Error display */}
      {error && (
        <div className="mb-6">
          <ErrorDisplay error={error} query={query} />
        </div>
      )}

      {/* Results section */}
      <div className="bg-card rounded-xl border border-border p-6">
        {loading ? (
          <ResultsSkeleton />
        ) : response ? (
          <>
            {response.type === "list" && (
              <ListResults
                response={response as ListQueryResponse}
                page={page}
                onPageChange={handlePageChange}
              />
            )}
            {response.type === "scalar" && (
              <ScalarResults response={response as ScalarQueryResponse} />
            )}
            {response.type === "grouped" && (
              <GroupedResults response={response as GroupedQueryResponse} />
            )}
          </>
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            <p className="text-lg mb-2">Enter a query to get started</p>
            <div className="text-sm space-y-1">
              <p><code className="px-1.5 py-0.5 rounded bg-muted font-mono text-xs">tss &gt; 100</code> — High-stress activities</p>
              <p><code className="px-1.5 py-0.5 rounded bg-muted font-mono text-xs">distance &gt; 50km AND date &gt;= START_OF_MONTH</code> — Long rides this month</p>
              <p><code className="px-1.5 py-0.5 rounded bg-muted font-mono text-xs">COUNT(*), AVG(tss) GROUP BY month</code> — Monthly statistics</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
