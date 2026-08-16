import * as React from "react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

interface MetricGroupCardProps {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}

export function MetricGroupCard({ icon, title, children }: MetricGroupCardProps) {
  return (
    <div className="bg-card rounded-xl border border-border p-5 card-hover transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h3 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">{title}</h3>
      </div>
      <div className="space-y-3">
        {children}
      </div>
    </div>
  );
}

interface MetricEntryProps {
  label: string;
  value: string;
  subtitle?: string;
  tooltip?: string;
  valueClass?: string;
  prominent?: boolean;
}

export function MetricEntry({ 
  label, 
  value, 
  subtitle,
  tooltip,
  valueClass,
  prominent 
}: MetricEntryProps) {
  const content = (
    <div className="flex justify-between items-baseline">
      <span className="text-muted-foreground text-sm">{label}</span>
      <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
        {value}
      </span>
    </div>
  );

  const withSubtitle = subtitle ? (
    <div className="flex justify-between items-baseline">
      <span className="text-muted-foreground text-sm">{label}</span>
      <div className="text-right">
        <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
          {value}
        </span>
        {subtitle && (
          <div className="text-xs text-primary">{subtitle}</div>
        )}
      </div>
    </div>
  ) : content;

  if (tooltip) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="cursor-help flex justify-between items-baseline">
            <span className="text-muted-foreground text-sm flex items-center gap-1">
              {label}
              <svg className="w-3 h-3 text-muted-foreground" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </span>
            <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
              {value}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {tooltip}
        </TooltipContent>
      </Tooltip>
    );
  }

  return withSubtitle;
}
