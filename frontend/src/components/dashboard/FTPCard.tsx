/**
 * FTP Card widget - Current FTP display
 */
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import type { ThresholdEntry, User } from "@/api";

interface FTPCardProps {
  currentThreshold: ThresholdEntry | null;
  user: User | null;
}

export function FTPCard({ currentThreshold, user }: FTPCardProps): JSX.Element {
  const navigate = useNavigate();
  
  const wPerKg = currentThreshold?.ftp_watts && user?.weight_kg
    ? currentThreshold.ftp_watts / user.weight_kg
    : null;

  return (
    <div 
      className="bg-card rounded-xl border border-border p-4 cursor-pointer card-hover"
      onClick={() => navigate("/settings")}
    >
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-card-title">FTP</h2>
        <span className="text-xs text-muted-foreground hover:text-foreground transition-fast">
          Edit →
        </span>
      </div>
      {currentThreshold?.ftp_watts ? (
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-foreground">{currentThreshold.ftp_watts}</span>
          <span className="text-3xl font-bold text-muted-foreground">W</span>
          {wPerKg && (
            <>
              <span className="text-3xl font-bold text-foreground ml-2">({wPerKg.toFixed(2)}</span>
              <span className="text-3xl font-bold text-muted-foreground">W/kg</span>
              <span className="text-3xl font-bold text-foreground">)</span>
            </>
          )}
        </div>
      ) : (
        <p className="text-muted-foreground text-sm">Not set</p>
      )}
    </div>
  );
}
