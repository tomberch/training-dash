import type { JSX } from "react";
import { Logo } from "./components/Logo";
import { NotificationBell } from "./components/NotificationBell";
import { SyncButton } from "./components/SyncButton";
import { UploadButton } from "./components/UploadButton";
import { UserMenu } from "./components/UserMenu";

interface HeaderProps {
  displayName: string | null;
  email: string;
  avatarPath: string | null;
  onLogout: () => void;
  onSettings: () => void;
  onUploadComplete?: () => void;
  onUploadTriggerRef?: (trigger: () => void) => void;
  showUpload?: boolean;
}

export function Header({
  displayName,
  email,
  avatarPath,
  onLogout,
  onSettings,
  onUploadComplete,
  onUploadTriggerRef,
  showUpload = true,
}: HeaderProps): JSX.Element {
  return (
    <header className="bg-card border-b border-border flex-shrink-0">
      <div className="px-6 py-3 flex items-center justify-between">
        <Logo size="md" showText={true} />
        
        <div className="flex items-center gap-4">
          <SyncButton className="gap-2" />
          
          {showUpload && (
            <UploadButton
              onUploadComplete={onUploadComplete}
              onUploadTriggerRef={onUploadTriggerRef}
              className="gap-2"
            />
          )}

          <NotificationBell />

          <UserMenu
            displayName={displayName}
            email={email}
            avatarPath={avatarPath}
            onLogout={onLogout}
            onSettings={onSettings}
            showChevron={true}
          />
        </div>
      </div>
    </header>
  );
}
