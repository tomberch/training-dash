/**
 * Dashboard empty state - shown when user has no activities
 */
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../PageHeader";

export function DashboardEmptyState(): JSX.Element {
  const navigate = useNavigate();

  return (
    <div className="p-8">
      <PageHeader title="Dashboard" />

      <div className="text-center mb-12">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-primary/10 mb-6">
          <svg className="w-10 h-10 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h2 className="text-page-title mb-3">Welcome to TrainDash</h2>
        <p className="text-lg text-muted-foreground max-w-md mx-auto">
          Get started by uploading your first activity or connecting to Xert/Garmin to sync automatically.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12 max-w-4xl mx-auto">
        {/* Step 1: Set thresholds */}
        <div 
          className="bg-card rounded-xl border border-border p-6 cursor-pointer hover:border-primary/50 transition-colors"
          onClick={() => navigate("/settings")}
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">1</div>
            <h3 className="font-semibold text-foreground">Set Your FTP</h3>
          </div>
          <p className="text-body-secondary">
            Configure your power thresholds to enable TSS, training load, and performance tracking.
          </p>
        </div>

        {/* Step 2: Connect or upload */}
        <div 
          className="bg-card rounded-xl border border-border p-6 cursor-pointer hover:border-primary/50 transition-colors"
          onClick={() => navigate("/settings")}
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">2</div>
            <h3 className="font-semibold text-foreground">Connect Accounts</h3>
          </div>
          <p className="text-body-secondary">
            Link your Xert or Garmin account to automatically sync your rides.
          </p>
        </div>

        {/* Step 3: Upload manually */}
        <div className="bg-card rounded-xl border border-border p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-muted-foreground text-sm font-bold">or</div>
            <h3 className="font-semibold text-foreground">Upload FIT Files</h3>
          </div>
          <p className="text-body-secondary">
            Use the "Upload FIT" button in the header to manually upload activity files.
          </p>
        </div>
      </div>

      {/* Quick stats preview */}
      <div className="bg-primary/5 rounded-xl border border-primary/20 p-6 max-w-4xl mx-auto">
        <h3 className="font-semibold text-foreground mb-4">What you'll see here</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span>Performance chart</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            <span>Power curve</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Weekly summary</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Recent activities</span>
          </div>
        </div>
      </div>
    </div>
  );
}
