import { useState, useEffect } from "react";
import type { RecordsResponse } from "./api";
import { fetchRecords } from "./api";
import { prsFromRecords, routePRsFromRecords } from "./prs";

export function RecordsView() {
  const [data, setData] = useState<RecordsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRecords()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div>Error: {error}</div>;
  if (!data) return <div>Loading...</div>;

  const lifetimePRs = prsFromRecords(data.lifetime_prs);
  const routePRs = routePRsFromRecords(data.route_prs);

  if (lifetimePRs.length === 0 && routePRs.length === 0) {
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

      {lifetimePRs.length > 0 && (
        <div style={{ marginBottom: "2rem" }}>
          <h2>Lifetime PRs</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
            {lifetimePRs.map((pr) => (
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
      )}

      {routePRs.length > 0 && (
        <div>
          <h2>Route PRs</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
            {routePRs.map((pr) => (
              <div
                key={pr.label}
                style={{
                  padding: "1rem 1.5rem",
                  background: "#e8f5e9",
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
      )}
    </div>
  );
}