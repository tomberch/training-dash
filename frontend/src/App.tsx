import { useState, useEffect } from "react";
import { ActivityList, Login } from "./ActivityList";
import { ActivityDetail } from "./ActivityDetail";
import { RecordsView } from "./RecordsView";
import { AdminView } from "./AdminView";
import { Header } from "./Header";
import { Settings } from "./Settings";
import { fetchMe } from "./api";
import type { User } from "./api";
import "./App.css";

type View = { type: "list" } | { type: "detail"; id: number } | { type: "records" } | { type: "admin" } | { type: "settings" };

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>({ type: "list" });
  const [refreshKey, setRefreshKey] = useState(0);

  // Check if user is logged in on mount
  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  function handleLogin(_isAdmin: boolean) {
    // Refetch user to get full user data
    fetchMe().then(setUser);
  }

  function handleLogout() {
    setUser(null);
    setView({ type: "list" });
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

  if (view.type === "settings") {
    return (
      <Settings
        user={user}
        onBack={() => setView({ type: "list" })}
        onUserUpdate={setUser}
      />
    );
  }

  if (view.type === "detail") {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <Header
          username={user.username}
          onLogout={handleLogout}
          onSettings={() => setView({ type: "settings" })}
          onUploadComplete={() => setRefreshKey((k) => k + 1)}
        />
        <ActivityDetail
          activityId={view.id}
          onBack={() => setView({ type: "list" })}
          unitSystem={user.unit_system}
        />
      </div>
    );
  }

  if (view.type === "records") {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <Header
          username={user.username}
          onLogout={handleLogout}
          onSettings={() => setView({ type: "settings" })}
          onUploadComplete={() => setRefreshKey((k) => k + 1)}
        />
        <div className="max-w-6xl mx-auto px-4 py-6">
          <button
            onClick={() => setView({ type: "list" })}
            className="mb-4 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            &larr; Back
          </button>
          <RecordsView unitSystem={user.unit_system} />
        </div>
      </div>
    );
  }

  if (view.type === "admin") {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <Header
          username={user.username}
          onLogout={handleLogout}
          onSettings={() => setView({ type: "settings" })}
          showUpload={false}
        />
        <AdminView onBack={() => setView({ type: "list" })} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header
        username={user.username}
        onLogout={handleLogout}
        onSettings={() => setView({ type: "settings" })}
        onUploadComplete={() => setRefreshKey((k) => k + 1)}
      />
      <div className="max-w-6xl mx-auto px-4 py-6">
        <ActivityList
          key={refreshKey}
          onSelect={(id) => setView({ type: "detail", id })}
          unitSystem={user.unit_system}
        />
        <div className="mt-6 flex gap-3">
          <button
            onClick={() => setView({ type: "records" })}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            Personal Records
          </button>
          {user.is_admin && (
            <button
              onClick={() => setView({ type: "admin" })}
              data-testid="admin-link"
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Admin
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
