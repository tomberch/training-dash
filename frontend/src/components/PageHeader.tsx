import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
}

export function PageHeader({
  title,
  subtitle,
}: PageHeaderProps) {
  return (
    <div className="mb-8">
      {/* Title row */}
      <h1 className="text-page-title">{title}</h1>
      {/* Subtitle row */}
      {subtitle && (
        <div className="text-body-secondary mt-2">
          {subtitle}
        </div>
      )}
    </div>
  );
}
