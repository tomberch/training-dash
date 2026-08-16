import * as React from "react";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
}

export function SectionHeader({ title, subtitle }: SectionHeaderProps): React.JSX.Element {
  return (
    <div className="mb-4 pb-2 border-b border-border">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      {subtitle && (
        <p className="text-body-secondary mt-0.5">{subtitle}</p>
      )}
    </div>
  );
}

interface ChartCardProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  onExpand?: () => void;
  children: React.ReactNode;
}

export function ChartCard({
  title,
  subtitle,
  action,
  onExpand,
  children,
}: ChartCardProps) {
  return (
    <div className="mb-6 bg-card rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          {subtitle && (
            <p className="text-caption">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {action}
          {onExpand && (
            <button
              onClick={onExpand}
              className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-fast"
              aria-label="Expand chart"
              title="Expand chart"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}
