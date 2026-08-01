import { useState, useEffect } from "react";
import type { Records } from "./api";
import { fetchRecords } from "./api";
import { prsFromRecords } from "./prs";

export function RecordsView() {
  const [records, setRecords] = useState<Records | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRecords()
      .then(setRecords)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div>Error: {error}</div>;
  if (!records) return <div>Loading...</div>;

  const prs = prsFromRecords(records);

  if (prs.length === 0) {
    return (
      <div>
        <h1>Records</h1>
        <p>No activities yet. Upload a FIT file to see your PRs.</p>
      </div>
    );
  }

  return (
    <div>
      <h1>Records</h1>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
        {prs.map((pr) => (
          <div
            key={pr.label}
            style={{
              padding: "1rem 1.5rem",
              background: "#f0f0f0",
              borderRadius: "8px",
              textAlign: "center",
              minWidth: "150px",
            }}
          >
            <div style={{ fontSize: "0.75rem", color: "#666" }}>{pr.label}</div>
            <div style={{ fontSize: "1.4rem", fontWeight: "bold" }}>{pr.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}