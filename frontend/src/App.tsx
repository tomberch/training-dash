import { useState } from "react";
import { ActivityList, Login } from "./ActivityList";
import { ActivityDetail } from "./ActivityDetail";
import { RecordsView } from "./RecordsView";
import { AdminView } from "./AdminView";
import "./App.css";

type View = { type: "list" } | { type: "detail"; id: number } | { type: "records" } | { type: "admin" };

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [view, setView] = useState<View>({ type: "list" });

  if (!loggedIn) {
    return <Login onLogin={(admin) => { setLoggedIn(true); setIsAdmin(admin); }} />;
  }

  if (view.type === "detail") {
    return (
      <ActivityDetail
        activityId={view.id}
        onBack={() => setView({ type: "list" })}
      />
    );
  }

  if (view.type === "records") {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <button
            onClick={() => setView({ type: "list" })}
            className="mb-4 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            &larr; Back
          </button>
          <RecordsView />
        </div>
      </div>
    );
  }

  if (view.type === "admin") {
    return <AdminView onBack={() => setView({ type: "list" })} />;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-6xl mx-auto px-4 py-6">
        <ActivityList onSelect={(id) => setView({ type: "detail", id })} />
        <div className="mt-6 flex gap-3">
          <button
            onClick={() => setView({ type: "records" })}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            Personal Records
          </button>
          {isAdmin && (
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
