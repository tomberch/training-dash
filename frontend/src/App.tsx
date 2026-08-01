import { useState } from "react";
import { ActivityList, Login } from "./ActivityList";
import { ActivityDetail } from "./ActivityDetail";
import { RecordsView } from "./RecordsView";
import "leaflet/dist/leaflet.css";
import "./App.css";

type View = { type: "list" } | { type: "detail"; id: number } | { type: "records" };

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [view, setView] = useState<View>({ type: "list" });

  if (!loggedIn) {
    return <Login onLogin={() => setLoggedIn(true)} />;
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

  return (
    <div>
      <ActivityList onSelect={(id) => setView({ type: "detail", id })} />
      <button onClick={() => setView({ type: "records" })}>Records</button>
    </div>
  );
}