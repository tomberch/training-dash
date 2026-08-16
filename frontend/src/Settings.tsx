import type { User } from "./api";
import { PageHeader } from "./components/PageHeader";
import { useSettingsTabs } from "./hooks/useSettingsTabs";
import { SettingsTabs, SettingsTabPanel } from "./components/SettingsTabs";
import {
  ProfileSettings,
  PreferencesSettings,
  MapSettings,
  TrainingSettings,
  IntegrationsSettings,
} from "./components/settings";

interface SettingsProps {
  user: User;
  onUserUpdate: (user: User) => void;
}

export function Settings({ user, onUserUpdate }: SettingsProps) {
  const { activeTab, setActiveTab } = useSettingsTabs();

  return (
    <div className="p-8">
      <PageHeader
        title="Settings"
        subtitle="Manage your profile, preferences, and integrations"
      />
      
      <SettingsTabs activeTab={activeTab} onTabChange={setActiveTab} />
      
      <SettingsTabPanel id="profile" activeTab={activeTab}>
        <div className="space-y-6">
          <ProfileSettings user={user} onUserUpdate={onUserUpdate} />
        </div>
      </SettingsTabPanel>

      <SettingsTabPanel id="preferences" activeTab={activeTab}>
        <div className="space-y-6">
          <PreferencesSettings user={user} onUserUpdate={onUserUpdate} />
          <MapSettings user={user} onUserUpdate={onUserUpdate} />
        </div>
      </SettingsTabPanel>

      <SettingsTabPanel id="training" activeTab={activeTab}>
        <TrainingSettings user={user} onUserUpdate={onUserUpdate} />
      </SettingsTabPanel>

      <SettingsTabPanel id="connections" activeTab={activeTab}>
        <IntegrationsSettings user={user} onUserUpdate={onUserUpdate} />
      </SettingsTabPanel>
    </div>
  );
}
