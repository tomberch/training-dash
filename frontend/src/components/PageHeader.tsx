import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: PageHeaderProps) {
  return (
    <div className="mb-8">
      {/* Title row */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-page-title">{title}</h1>
          {/* Subtitle row */}
          {subtitle && (
            <div className="text-body-secondary mt-2">
              {subtitle}
            </div>
          )}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
    </div>
  );
}
