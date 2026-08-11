import type { JSX } from "react";
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
    <header className="bg-card border-b border-border">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-end">
        <div className="flex items-center gap-4">
          {showUpload && (
            <UploadButton
              onUploadComplete={onUploadComplete}
              onUploadTriggerRef={onUploadTriggerRef}
              className="gap-2"
            />
          )}

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
