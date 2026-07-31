import { useState } from "react";
import { ActivityList, Login } from "./ActivityList";
import { ActivityDetail } from "./ActivityDetail";
import "leaflet/dist/leaflet.css";
import "./App.css";

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [selectedActivity, setSelectedActivity] = useState<number | null>(null);

  if (!loggedIn) {
    return <Login onLogin={() => setLoggedIn(true)} />;
  }

  if (selectedActivity !== null) {
    return (
      <ActivityDetail
        activityId={selectedActivity}
        onBack={() => setSelectedActivity(null)}
      />
    );
  }

  return <ActivityList onSelect={setSelectedActivity} />;
}