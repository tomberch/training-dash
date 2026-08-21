import { useState, useEffect, lazy, Suspense, useRef } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams } from "react-router-dom";
import { ActivityList, Login, PendingApproval } from "./ActivityList";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { fetchMe, fetchThresholds, fetchActivities } from "./api";
import type { User } from "./api";
import "./App.css";

import { OnboardingDialog } from "./components/OnboardingDialog";
import { CommandMenu } from "./components/CommandMenu";
import { Toaster } from "./components/ui/sonner";
import { UserContext } from "./contexts/UserContext";

// Lazy-loaded page components for code splitting
const ActivityDetail = lazy(() => import("./ActivityDetail").then(m => ({ default: m.ActivityDetail })));
const RecordsView = lazy(() => import("./RecordsView").then(m => ({ default: m.RecordsView })));
const AdminView = lazy(() => import("./AdminView").then(m => ({ default: m.AdminView })));
const SystemDashboard = lazy(() => import("./SystemDashboard").then(m => ({ default: m.SystemDashboard })));
const Settings = lazy(() => import("./Settings").then(m => ({ default: m.Settings })));
const Dashboard = lazy(() => import("./pages/Dashboard").then(m => ({ default: m.Dashboard })));
const PMCView = lazy(() => import("./pages/PMCView").then(m => ({ default: m.PMCView })));
const PowerCurveView = lazy(() => import("./pages/PowerCurveView").then(m => ({ default: m.PowerCurveView })));
const ActivityTable = lazy(() => import("./pages/ActivityTable").then(m => ({ default: m.ActivityTable })));
const AnalyzePage = lazy(() => import("./pages/AnalyzePage").then(m => ({ default: m.AnalyzePage })));
const ComparePage = lazy(() => import("./pages/ComparePage").then(m => ({ default: m.ComparePage })));
const AthletePage = lazy(() => import("./pages/AthletePage").then(m => ({ default: m.AthletePage })));
const PrototypeEventDetail = lazy(() => import("./pages/prototype-event-detail").then(m => ({ default: m.PrototypeEventDetail })));
const PrototypeEventList = lazy(() => import("./pages/prototype-event-list").then(m => ({ default: m.PrototypeEventList })));
const PrototypeSegments = lazy(() => import("./pages/prototype-segments").then(m => ({ default: m.PrototypeSegments })));
const QueryPage = lazy(() => import("./pages/QueryPage").then(m => ({ default: m.QueryPage })));
const EventsPage = lazy(() => import("./pages/EventsPage").then(m => ({ default: m.EventsPage })));
const EventDetailPage = lazy(() => import("./pages/EventDetailPage").then(m => ({ default: m.EventDetailPage })));
const EventFormPage = lazy(() => import("./pages/EventFormPage").then(m => ({ default: m.EventFormPage })));
const EventEditPage = lazy(() => import("./pages/EventEditPage").then(m => ({ default: m.EventEditPage })));
const GearPage = lazy(() => import("./pages/GearPage").then(m => ({ default: m.GearPage })));
const PlanDetail = lazy(() => import("./pages/RacePlanner").then(m => ({ default: m.PlanDetail })));

// Page loading skeleton for Suspense fallback
function PageLoadingSkeleton() {
  return (
    <div className="flex-1 p-6">
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-muted rounded w-1/4"></div>
        <div className="h-64 bg-muted rounded"></div>
        <div className="h-32 bg-muted rounded"></div>
      </div>
    </div>
  );
}

// Initialize theme on app load
function initializeTheme() {
  // Skip in test environment where DOM APIs may not be available
  if (typeof window === "undefined" || !window.matchMedia) {
    return;
  }
  
  // Check for stored preference
  const stored = localStorage.getItem("traindash-theme");
  
  let theme: "latte" | "mocha" | "midnight";
  
  if (stored === "latte" || stored === "mocha" || stored === "midnight") {
    theme = stored;
  } else if (stored === "system" || !stored) {
    // Follow system preference - use midnight for dark mode
    theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "midnight" : "latte";
  } else {
    theme = "latte"; // Default fallback
  }
  
  // Apply theme
  document.documentElement.setAttribute("data-theme", theme);
  if (theme === "mocha" || theme === "midnight") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

// Run theme initialization immediately
initializeTheme();

// Layout wrapper with sidebar
function AppLayout({ user, onLogout, onUserUpdate }: { 
  user: User; 
  onLogout: () => void;
  onUserUpdate: (user: User) => void;
}) {
  const [refreshKey, setRefreshKey] = useState(0);
  const uploadTriggerRef = useRef<(() => void) | null>(null);
  const navigate = useNavigate();

  return (
    <div className="h-screen bg-background flex flex-col overflow-hidden">
      {/* Full-width header at top - fixed */}
      <Header
        displayName={user.display_name}
        email={user.email}
        avatarPath={user.avatar_path}
        onLogout={onLogout}
        onSettings={() => navigate("/settings")}
        onUploadComplete={() => setRefreshKey((k) => k + 1)}
        onUploadTriggerRef={(trigger) => { uploadTriggerRef.current = trigger; }}
      />
      
      {/* Sidebar + Content below header */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar isAdmin={user.is_admin} />
        <CommandMenu 
          onUpload={() => uploadTriggerRef.current?.()} 
          isAdmin={user.is_admin}
        />
        <main className="flex-1 overflow-auto">
          <div className="max-w-7xl mx-auto">
            <Suspense fallback={<PageLoadingSkeleton />}>
            <Routes>
              <Route path="/" element={
                <Dashboard />
              } />
              <Route 
                path="/activities" 
                element={
                  <ActivityList
                    key={refreshKey}
                    onSelect={(id) => navigate(`/activities/${id}`)}
                    unitSystem={user.unit_system}
                  />
                } 
              />
              <Route 
                path="/activities/table" 
                element={
                  <ActivityTable
                    unitSystem={user.unit_system}
                  />
                } 
              />
              <Route 
                path="/activities/:id" 
                element={<ActivityDetailWrapper unitSystem={user.unit_system} />} 
              />
              <Route path="/pmc" element={<PMCView />} />
              <Route path="/power-curve" element={<PowerCurveView />} />
              <Route path="/analyze" element={<AnalyzePage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/query" element={<QueryPage />} />
              <Route path="/events" element={<EventsPage />} />
              <Route path="/events/new" element={<EventFormPage />} />
              <Route path="/events/:id" element={<EventDetailPage />} />
              <Route path="/events/:id/edit" element={<EventEditPage />} />
              <Route path="/athlete" element={<AthletePage user={user} onUserUpdate={onUserUpdate} />} />
              <Route path="/prototype/event-detail" element={<PrototypeEventDetail />} />
              <Route path="/prototype/event-list" element={<PrototypeEventList />} />
              <Route path="/prototype/segments" element={<PrototypeSegments />} />
              <Route 
                path="/records" 
                element={<RecordsView unitSystem={user.unit_system} />} 
              />
              <Route 
                path="/settings" 
                element={
                  <SettingsWrapper 
                    user={user} 
                    onUserUpdate={onUserUpdate}
                  />
                } 
              />
              <Route 
                path="/settings/gear" 
                element={<GearPage unitSystem={user.unit_system} />} 
              />
              <Route path="/race-planner/plans/:planId" element={<PlanDetail />} />
              {user.is_admin && (
                <Route path="/admin" element={<AdminViewWrapper />} />
              )}
              {user.is_admin && (
                <Route path="/admin/system" element={<SystemDashboardWrapper />} />
              )}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}

import type { UnitSystem } from "./format";

// Wrapper components to handle navigation from within pages
function ActivityDetailWrapper({ unitSystem }: { unitSystem: UnitSystem }) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  if (!id) return <Navigate to="/activities" replace />;
  
  return (
    <ActivityDetail
      activityId={id}
      onBack={() => navigate("/activities")}
      unitSystem={unitSystem}
    />
  );
}

function SettingsWrapper({ 
  user, 
  onUserUpdate,
}: { 
  user: User; 
  onUserUpdate: (user: User) => void;
}) {
  return (
    <Settings
      user={user}
      onUserUpdate={onUserUpdate}
    />
  );
}

function AdminViewWrapper() {
  const navigate = useNavigate();
  
  return (
    <AdminView 
      onBack={() => navigate("/")} 
      onSystemDashboard={() => navigate("/admin/system")}
    />
  );
}

function SystemDashboardWrapper() {
  const navigate = useNavigate();
  
  return (
    <SystemDashboard onBack={() => navigate("/admin")} />
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(false);

  // Check if user is logged in on mount
  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  function handleLogin(_result: { is_admin: boolean; is_approved: boolean }) {
    // Refetch user, then check whether user has activities or thresholds — show onboarding if neither
    fetchMe().then((u) => {
      setUser(u);
      if (u.is_approved) {
        // Check both activities and thresholds - show onboarding only if BOTH are empty
        Promise.all([
          fetchActivities(1, 1).catch(() => ({ activities: [], pagination: { page: 1, per_page: 1, total: 0, total_pages: 0 } })),
          fetchThresholds().catch(() => [])
        ]).then(([activitiesResult, thresholds]) => {
          const hasActivities = activitiesResult.activities.length > 0;
          const hasThresholds = thresholds.length > 0;
          if (!hasActivities && !hasThresholds) {
            setShowOnboarding(true);
          }
        });
      }
    });
  }

  function handleLogout() {
    setUser(null);
    setShowOnboarding(false);
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <svg className="w-8 h-8 text-primary animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-muted-foreground text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  // Show pending approval screen if user is not approved
  if (!user.is_approved) {
    return <PendingApproval onLogout={handleLogout} />;
  }

  return (
    <UserContext.Provider value={{ user, updateUser: setUser }}>
      <BrowserRouter>
        <AppLayout user={user} onLogout={handleLogout} onUserUpdate={setUser} />
        <OnboardingDialog
          open={showOnboarding}
          onDone={() => setShowOnboarding(false)}
        />
        <Toaster />
      </BrowserRouter>
    </UserContext.Provider>
  );
}
