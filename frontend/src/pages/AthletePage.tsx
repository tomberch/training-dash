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

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "thresholds", label: "Thresholds" },
  { value: "body", label: "Body" },
  { value: "fitness", label: "Fitness" },
  { value: "recovery", label: "Recovery" },
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
    <div className="max-w-4xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-bold text-foreground mb-6">Athlete Profile</h1>

      <Tabs value={currentTab} onValueChange={handleTabChange}>
        <TabsList className="w-full justify-start overflow-x-auto">
          {TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
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
