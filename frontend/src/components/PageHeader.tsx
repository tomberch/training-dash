import type { ReactNode } from "react";
import { UploadButton } from "./UploadButton";
import { UserMenu } from "./UserMenu";

interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  /** User info for inline controls (when global header is hidden) */
  user?: {
    display_name: string | null;
    email: string;
    avatar_path: string | null;
  };
  onLogout?: () => void;
  onSettings?: () => void;
  onUploadComplete?: () => void;
  onUploadTriggerRef?: (trigger: () => void) => void;
}

export function PageHeader({
  title,
  subtitle,
  user,
  onLogout,
  onSettings,
  onUploadComplete,
  onUploadTriggerRef,
}: PageHeaderProps) {
  const showControls = user && onLogout && onSettings;

  return (
    <div className="mb-8">
      {/* Title row */}
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-page-title">{title}</h1>
        {showControls && (
          <div className="flex items-center gap-4">
            <UploadButton
              onUploadComplete={onUploadComplete}
              onUploadTriggerRef={onUploadTriggerRef}
            />
            <UserMenu
              displayName={user.display_name}
              email={user.email}
              avatarPath={user.avatar_path}
              onLogout={onLogout}
              onSettings={onSettings}
            />
          </div>
        )}
      </div>
      {/* Subtitle row */}
      {subtitle && (
        <div className="text-body-secondary">
          {subtitle}
        </div>
      )}
    </div>
  );
}
