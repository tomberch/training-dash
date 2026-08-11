import { useSearchParams } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  AthleteOverview,
  AthleteThresholds,
  AthleteBody,
  AthleteFitness,
  AthleteRecovery,
} from "./athlete";
import type { User } from "@/api";
import { CheckCircle, Lock, Scale, Zap, Heart } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";

const TABS = [
  { value: "overview", label: "Overview", icon: CheckCircle },
  { value: "thresholds", label: "Thresholds", icon: Lock },
  { value: "body", label: "Body", icon: Scale },
  { value: "fitness", label: "Fitness", icon: Zap },
  { value: "recovery", label: "Recovery", icon: Heart },
] as const;

type TabValue = (typeof TABS)[number]["value"];

function isValidTab(tab: string | null): tab is TabValue {
  return TABS.some((t) => t.value === tab);
}

interface AthletePageProps {
  user: User;
  onUserUpdate: (user: User) => void;
}

export function AthletePage({ user, onUserUpdate }: AthletePageProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const currentTab = isValidTab(tabParam) ? tabParam : "overview";

  function handleTabChange(value: string) {
    if (value === "overview") {
      // Remove tab param for default tab to keep URL clean
      searchParams.delete("tab");
    } else {
      searchParams.set("tab", value);
    }
    setSearchParams(searchParams, { replace: true });
  }

  return (
    <div className="p-8">
      <PageHeader
        title="Athlete Profile"
        subtitle="Your physiological data and training thresholds"
      />

      <Tabs value={currentTab} onValueChange={handleTabChange}>
        <TabsList className="w-full justify-start overflow-x-auto mb-6">
          {TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value} className="gap-2">
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview">
          <AthleteOverview user={user} />
        </TabsContent>
        <TabsContent value="thresholds">
          <AthleteThresholds />
        </TabsContent>
        <TabsContent value="body">
          <AthleteBody user={user} onUserUpdate={onUserUpdate} />
        </TabsContent>
        <TabsContent value="fitness">
          <AthleteFitness />
        </TabsContent>
        <TabsContent value="recovery">
          <AthleteRecovery />
        </TabsContent>
      </Tabs>
    </div>
  );
}
