import { useState } from "react";
import { ActivityList, Login } from "./ActivityList";
import { ActivityDetail } from "./ActivityDetail";
import { RecordsView } from "./RecordsView";
import { AdminView } from "./AdminView";
import "leaflet/dist/leaflet.css";
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
      <div>
        <button onClick={() => setView({ type: "list" })}>Back</button>
        <RecordsView />
      </div>
    );
  }

  if (view.type === "admin") {
    return <AdminView onBack={() => setView({ type: "list" })} />;
  }

  return (
    <div>
      <ActivityList onSelect={(id) => setView({ type: "detail", id })} />
      <button onClick={() => setView({ type: "records" })}>Records</button>
      {isAdmin && <button onClick={() => setView({ type: "admin" })} data-testid="admin-link">Admin</button>}
    </div>
  );
}