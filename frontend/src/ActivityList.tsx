import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import type { Activity, PaginationMeta } from "./api";
import { ApiError, fetchActivities, login, register } from "./api";
import { formatDistance, formatTime, formatElevation, formatActivityDate } from "./format";
import type { UnitSystem } from "./format";
import { ErrorDisplay } from "./ErrorDisplay";
import { EmptyState } from "@/components/ui/empty-state";
import { Logo } from "./components/Logo";
import { PolylineMap } from "./components/PolylineMap";

// Activity row component (Xert-inspired)
function ActivityRow({ 
  activity, 
  onSelect, 
  unitSystem 
}: { 
  activity: Activity; 
  onSelect: (id: string) => void; 
  unitSystem: UnitSystem;
}) {
  return (
    <div 
      onClick={() => onSelect(activity.id)}
      className="flex items-center gap-4 p-4 bg-card border-b border-border cursor-pointer hover:bg-muted/50 transition-fast"
    >
      {/* Map thumbnail */}
      <div className="w-36 h-24 flex-shrink-0">
        <PolylineMap 
          polyline={activity.map_polyline} 
          className="w-full h-full"
          showMarkers={true}
        />
      </div>
      
      {/* Activity info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-medium text-foreground truncate">
            {activity.title || formatActivityDate(activity.started_at, activity.utc_offset_minutes)}
          </h3>
          {activity.is_breakthrough && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-warning-foreground bg-warning/90 rounded-full">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              Breakthrough
            </span>
          )}
        </div>
        {activity.title && (
          <p className="text-sm text-muted-foreground mt-0.5">
            {formatActivityDate(activity.started_at, activity.utc_offset_minutes)}
          </p>
        )}
      </div>
      
      {/* Metrics */}
      <div className="hidden sm:flex items-center gap-6 text-sm">
        <div className="text-center">
          <div className="font-semibold text-foreground tabular-nums">
            {formatDistance(activity.total_distance_m, unitSystem)}
          </div>
          <div className="text-xs text-muted-foreground">Distance</div>
        </div>
        <div className="text-center">
          <div className="font-semibold text-foreground tabular-nums">
            {formatTime(activity.moving_time_s)}
          </div>
          <div className="text-xs text-muted-foreground">Time</div>
        </div>
        <div className="text-center">
          <div className="font-semibold text-foreground tabular-nums">
            {formatElevation(activity.elevation_gain_m, unitSystem)}
          </div>
          <div className="text-xs text-muted-foreground">Elev</div>
        </div>
        {activity.tss != null && (
          <div className="text-center">
            <div className="font-semibold text-foreground tabular-nums">
              {Math.round(activity.tss)}
            </div>
            <div className="text-xs text-muted-foreground">TSS</div>
          </div>
        )}
        {activity.avg_power_w != null && (
          <div className="text-center">
            <div className="font-semibold text-foreground tabular-nums">
              {activity.avg_power_w}W
            </div>
            <div className="text-xs text-muted-foreground">Avg Power</div>
          </div>
        )}
        {activity.avg_hr_bpm != null && (
          <div className="text-center">
            <div className="font-semibold text-foreground tabular-nums">
              {activity.avg_hr_bpm}
            </div>
            <div className="text-xs text-muted-foreground">Avg HR</div>
          </div>
        )}
      </div>
      
      {/* Mobile metrics (compact) */}
      <div className="flex sm:hidden items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium">{formatDistance(activity.total_distance_m, unitSystem)}</span>
        <span>•</span>
        <span>{formatTime(activity.moving_time_s)}</span>
      </div>
    </div>
  );
}

// Pagination component
function Pagination({
  pagination,
  onPageChange,
}: {
  pagination: PaginationMeta;
  onPageChange: (page: number) => void;
}) {
  const { page, total_pages } = pagination;
  
  // Generate page numbers to show
  const getPageNumbers = () => {
    const pages: (number | "...")[] = [];
    
    if (total_pages <= 7) {
      // Show all pages if 7 or fewer
      for (let i = 1; i <= total_pages; i++) pages.push(i);
    } else {
      // Always show first page
      pages.push(1);
      
      if (page > 3) pages.push("...");
      
      // Show pages around current
      for (let i = Math.max(2, page - 1); i <= Math.min(total_pages - 1, page + 1); i++) {
        pages.push(i);
      }
      
      if (page < total_pages - 2) pages.push("...");
      
      // Always show last page
      pages.push(total_pages);
    }
    
    return pages;
  };
  
  if (total_pages <= 1) return null;
  
  return (
    <div className="flex items-center justify-center gap-1 mt-6">
      {/* Previous button */}
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page === 1}
        className="px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-fast"
      >
        Previous
      </button>
      
      {/* Page numbers */}
      <div className="flex items-center gap-1">
        {getPageNumbers().map((p, i) => (
          p === "..." ? (
            <span key={`ellipsis-${i}`} className="px-2 text-muted-foreground">...</span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`w-10 h-10 text-sm font-medium rounded-lg transition-fast ${
                p === page
                  ? "bg-primary text-primary-foreground"
                  : "text-foreground bg-card border border-border hover:bg-muted"
              }`}
            >
              {p}
            </button>
          )
        ))}
      </div>
      
      {/* Next button */}
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page === total_pages}
        className="px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-fast"
      >
        Next
      </button>
    </div>
  );
}

export function ActivityList({
  onSelect,
  unitSystem = "metric",
}: {
  onSelect: (id: string) => void;
  unitSystem?: UnitSystem;
}) {
  const navigate = useNavigate();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | ApiError | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchActivities(currentPage, 20)
      .then((result) => {
        setActivities(result.activities);
        setPagination(result.pagination);
      })
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, [currentPage]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    // Scroll to top when changing pages
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (error) {
    return <ErrorDisplay error={error} context="loading activities" />;
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold text-foreground">Activities</h1>
          <button
            onClick={() => navigate("/activities/table")}
            className="text-sm text-primary hover:text-primary/80 flex items-center gap-1 transition"
            title="View as table"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            Table view
          </button>
        </div>
        {pagination && (
          <span className="text-sm text-muted-foreground">
            {pagination.total} {pagination.total === 1 ? "activity" : "activities"}
          </span>
        )}
      </div>

      {loading ? (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 p-4 border-b border-border last:border-b-0 animate-pulse">
              <div className="w-36 h-24 bg-muted rounded"></div>
              <div className="flex-1">
                <div className="h-5 w-48 bg-muted rounded mb-2"></div>
                <div className="h-4 w-32 bg-muted rounded"></div>
              </div>
            </div>
          ))}
        </div>
      ) : activities.length === 0 ? (
        <div className="bg-card rounded-lg border border-border">
          <EmptyState
            icon={
              <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
            }
            title="No activities yet"
            description="Upload a FIT file or connect your Xert account to start tracking your rides."
          />
        </div>
      ) : (
        <>
          <div className="bg-card rounded-lg border border-border overflow-hidden">
            {activities.map((a) => (
              <ActivityRow
                key={a.id}
                activity={a}
                onSelect={onSelect}
                unitSystem={unitSystem}
              />
            ))}
          </div>
          
          {pagination && (
            <Pagination pagination={pagination} onPageChange={handlePageChange} />
          )}
        </>
      )}
    </div>
  );
}

export function Login({
  onLogin,
}: {
  onLogin: (user: { is_admin: boolean; is_approved: boolean }) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "login") {
        const result = await login(email, password);
        if (result) {
          onLogin({ is_admin: result.is_admin ?? false, is_approved: result.is_approved ?? true });
        } else {
          setError("Invalid credentials");
        }
      } else {
        // Register mode
        if (password !== confirmPassword) {
          setError("Passwords do not match");
          setLoading(false);
          return;
        }
        if (password.length < 8) {
          setError("Password must be at least 8 characters");
          setLoading(false);
          return;
        }
        const result = await register(email, password);
        onLogin({ is_admin: result.is_admin, is_approved: result.is_approved });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="bg-card rounded-xl shadow-lg border border-border p-8">
          <div className="flex justify-center mb-6">
            <Logo size="lg" />
          </div>
          
          {error && (
            <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
              {error}
            </div>
          )}

          {/* OAuth Buttons */}
          <div className="space-y-3 mb-6">
            <a
              href="/auth/google"
              className="flex items-center justify-center w-full px-4 py-2.5 border border-border rounded-lg bg-card hover:bg-muted transition-fast"
            >
              <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span className="text-sm font-medium text-foreground">
                {mode === "login" ? "Continue with Google" : "Sign up with Google"}
              </span>
            </a>

            <a
              href="/auth/github"
              className="flex items-center justify-center w-full px-4 py-2.5 border border-border rounded-lg bg-card hover:bg-muted transition-fast"
            >
              <svg className="w-5 h-5 mr-3 text-foreground" fill="currentColor" viewBox="0 0 24 24">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0012 2z"/>
              </svg>
              <span className="text-sm font-medium text-foreground">
                {mode === "login" ? "Continue with GitHub" : "Sign up with GitHub"}
              </span>
            </a>
          </div>

          {/* Divider */}
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-card text-muted-foreground">or</span>
            </div>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 border border-input-border rounded-lg bg-input text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                placeholder="Enter email"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-input-border rounded-lg bg-input text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                placeholder="Enter password"
                required
              />
            </div>

            {mode === "register" && (
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-input-border rounded-lg bg-input text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                  placeholder="Confirm password"
                  required
                />
              </div>
            )}
            
            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2 px-4 bg-primary hover:bg-primary/80 disabled:bg-primary/50 text-primary-foreground font-medium rounded-lg transition-fast focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            >
              {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="text-sm text-primary hover:underline"
            >
              {mode === "login" ? "Don't have an account? Register" : "Already have an account? Sign in"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function PendingApproval({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md text-center">
        <div className="bg-card rounded-xl shadow-lg border border-border p-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-warning/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">
            Account Pending Approval
          </h1>
          <p className="text-muted-foreground mb-6">
            Your account has been created and is waiting for administrator approval. 
            You'll be able to access the dashboard once your account is approved.
          </p>
          <button
            onClick={onLogout}
            className="px-4 py-2 text-sm font-medium text-foreground bg-muted rounded-lg hover:bg-muted/80 transition-fast"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
