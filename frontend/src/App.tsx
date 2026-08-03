import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams } from "react-router-dom";
import { ActivityList, Login, PendingApproval } from "./ActivityList";
import { ActivityDetail } from "./ActivityDetail";
import { RecordsView } from "./RecordsView";
import { AdminView } from "./AdminView";
import { Header } from "./Header";
import { Settings } from "./Settings";
import { Sidebar } from "./Sidebar";
import { Dashboard } from "./pages/Dashboard";
import { PMCView } from "./pages/PMCView";
import { PowerCurveView } from "./pages/PowerCurveView";
import { fetchMe } from "./api";
import type { User } from "./api";
import "./App.css";

// Layout wrapper with sidebar
function AppLayout({ user, onLogout, onUserUpdate }: { 
  user: User; 
  onLogout: () => void;
  onUserUpdate: (user: User) => void;
}) {
  const [refreshKey, setRefreshKey] = useState(0);
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar isAdmin={user.is_admin} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          displayName={user.display_name}
          email={user.email}
          avatarPath={user.avatar_path}
          onLogout={onLogout}
          onSettings={() => navigate("/settings")}
          onUploadComplete={() => setRefreshKey((k) => k + 1)}
        />
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route 
              path="/activities" 
              element={
                <div className="max-w-6xl mx-auto px-4 py-6">
                  <ActivityList
                    key={refreshKey}
                    onSelect={(id) => navigate(`/activities/${id}`)}
                    unitSystem={user.unit_system}
                  />
                </div>
              } 
            />
            <Route 
              path="/activities/:id" 
              element={<ActivityDetailWrapper unitSystem={user.unit_system} />} 
            />
            <Route path="/pmc" element={<PMCView />} />
            <Route path="/power-curve" element={<PowerCurveView />} />
            <Route 
              path="/records" 
              element={
                <div className="max-w-6xl mx-auto px-4 py-6">
                  <RecordsView unitSystem={user.unit_system} />
                </div>
              } 
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
            {user.is_admin && (
              <Route path="/admin" element={<AdminViewWrapper />} />
            )}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
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
      activityId={parseInt(id, 10)}
      onBack={() => navigate("/activities")}
      unitSystem={unitSystem}
    />
  );
}

function SettingsWrapper({ user, onUserUpdate }: { user: User; onUserUpdate: (user: User) => void }) {
  const navigate = useNavigate();
  
  return (
    <Settings
      user={user}
      onBack={() => navigate(-1)}
      onUserUpdate={onUserUpdate}
    />
  );
}

function AdminViewWrapper() {
  const navigate = useNavigate();
  
  return (
    <AdminView onBack={() => navigate("/")} />
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Check if user is logged in on mount
  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  function handleLogin(_result: { is_admin: boolean; is_approved: boolean }) {
    // Refetch user to get full user data
    fetchMe().then(setUser);
  }

  function handleLogout() {
    setUser(null);
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
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
    <BrowserRouter>
      <AppLayout user={user} onLogout={handleLogout} onUserUpdate={setUser} />
    </BrowserRouter>
  );
}
