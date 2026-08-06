import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { useTheme } from "@/hooks/useTheme";

// Icons
import {
  HomeIcon,
  ListIcon,
  LayersIcon,
  ChartBarIcon,
  BoltIcon,
  TrophyIcon,
  CogIcon,
  ArrowRightLeftIcon,
  UploadIcon,
  SunIcon,
  MoonIcon,
} from "lucide-react";

interface CommandMenuProps {
  onUpload?: () => void;
  isAdmin?: boolean;
}

interface CommandItem {
  id: string;
  label: string;
  shortcut?: string;
  icon: React.ReactNode;
  action: () => void;
  keywords?: string[];
}

export function CommandMenu({ onUpload, isAdmin = false }: CommandMenuProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const [awaitingG, setAwaitingG] = useState(false);
  const gTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();
  const { resolvedTheme, setTheme } = useTheme();

  // Single source of truth for navigation routes.
  // The G-shortcut key, command palette entry, and keyboard handler all derive from this.
  const NAV_ROUTES = [
    { key: "d", path: "/",            id: "nav-dashboard",   label: "Go to Dashboard",   shortcut: "G D", icon: <HomeIcon className="h-4 w-4" />,          keywords: ["home", "overview"] },
    { key: "a", path: "/activities",  id: "nav-activities",  label: "Go to Activities",  shortcut: "G A", icon: <ListIcon className="h-4 w-4" />,           keywords: ["rides", "workouts", "list"] },
    { key: "z", path: "/analyze",     id: "nav-analyze",     label: "Go to Analyze",     shortcut: "G Z", icon: <LayersIcon className="h-4 w-4" />,         keywords: ["details", "deep dive"] },
    { key: "c", path: "/compare",     id: "nav-compare",     label: "Go to Compare",     shortcut: "G C", icon: <ArrowRightLeftIcon className="h-4 w-4" />, keywords: ["side by side", "diff"] },
    { key: "p", path: "/pmc",         id: "nav-pmc",         label: "Go to PMC",         shortcut: "G P", icon: <ChartBarIcon className="h-4 w-4" />,       keywords: ["fitness", "fatigue", "form", "performance management chart"] },
    { key: "w", path: "/power-curve", id: "nav-power-curve", label: "Go to Power Curve", shortcut: "G W", icon: <BoltIcon className="h-4 w-4" />,           keywords: ["watts", "cp", "ftp"] },
    { key: "r", path: "/records",     id: "nav-records",     label: "Go to Records",     shortcut: "G R", icon: <TrophyIcon className="h-4 w-4" />,         keywords: ["prs", "personal records", "best"] },
    { key: "s", path: "/settings",    id: "nav-settings",    label: "Go to Settings",    shortcut: "G S", icon: <CogIcon className="h-4 w-4" />,            keywords: ["preferences", "config"] },
  ] as const;

  // Derived: command palette entries for navigation
  const navigationCommands: CommandItem[] = NAV_ROUTES.map((r) => ({
    id: r.id,
    label: r.label,
    shortcut: r.shortcut,
    icon: r.icon,
    action: () => navigate(r.path),
    keywords: [...r.keywords],
  }));

  // Derived: G + letter shortcut map
  const gShortcuts: Record<string, () => void> = Object.fromEntries(
    NAV_ROUTES.map((r) => [r.key, () => navigate(r.path)])
  );

  // Action commands (single key)
  const actionCommands: CommandItem[] = [
    {
      id: "action-upload",
      label: "Upload FIT File",
      shortcut: "U",
      icon: <UploadIcon className="h-4 w-4" />,
      action: () => { onUpload?.(); },
      keywords: ["import", "add activity"],
    },
    {
      id: "action-theme",
      label: resolvedTheme === "latte" ? "Switch to Dark Mode" : "Switch to Light Mode",
      shortcut: "T",
      icon: resolvedTheme === "latte" ? <MoonIcon className="h-4 w-4" /> : <SunIcon className="h-4 w-4" />,
      action: () => { setTheme(resolvedTheme === "latte" ? "mocha" : "latte"); },
      keywords: ["dark", "light", "appearance"],
    },
  ];

  // Single-key shortcuts
  const singleKeyShortcuts: Record<string, () => void> = {
    u: () => onUpload?.(),
    t: () => setTheme(resolvedTheme === "latte" ? "mocha" : "latte"),
  };

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in an input
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;

      // Cmd/Ctrl + K opens command palette
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
        return;
      }

      // Don't process other shortcuts when palette is open or typing
      if (open || isInput) return;

      const key = e.key.toLowerCase();

      // Handle G + letter navigation
      if (awaitingG) {
        if (gShortcuts[key]) {
          e.preventDefault();
          gShortcuts[key]();
        }
        setAwaitingG(false);
        if (gTimeoutRef.current) {
          clearTimeout(gTimeoutRef.current);
          gTimeoutRef.current = null;
        }
        return;
      }

      // Start G sequence
      if (key === "g") {
        setAwaitingG(true);
        // Reset after 1 second if no follow-up key
        gTimeoutRef.current = setTimeout(() => {
          setAwaitingG(false);
        }, 1000);
        return;
      }

      // Single-key shortcuts
      if (singleKeyShortcuts[key]) {
        e.preventDefault();
        singleKeyShortcuts[key]();
      }
    },
    [open, awaitingG, navigate, onUpload, setTheme, resolvedTheme]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (gTimeoutRef.current) {
        clearTimeout(gTimeoutRef.current);
      }
    };
  }, [handleKeyDown]);

  const runCommand = useCallback((command: () => void) => {
    setOpen(false);
    command();
  }, []);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigation">
          {navigationCommands.map((cmd) => (
            <CommandItem
              key={cmd.id}
              value={`${cmd.label} ${cmd.keywords?.join(" ") ?? ""}`}
              onSelect={() => runCommand(cmd.action)}
              aria-keyshortcuts={cmd.shortcut?.toLowerCase().replace(" ", "+")}
            >
              {cmd.icon}
              <span>{cmd.label}</span>
              {cmd.shortcut && <CommandShortcut>{cmd.shortcut}</CommandShortcut>}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Actions">
          {actionCommands.map((cmd) => (
            <CommandItem
              key={cmd.id}
              value={`${cmd.label} ${cmd.keywords?.join(" ") ?? ""}`}
              onSelect={() => runCommand(cmd.action)}
              aria-keyshortcuts={cmd.shortcut?.toLowerCase()}
            >
              {cmd.icon}
              <span>{cmd.label}</span>
              {cmd.shortcut && <CommandShortcut>{cmd.shortcut}</CommandShortcut>}
            </CommandItem>
          ))}
        </CommandGroup>
        {isAdmin && (
          <CommandGroup heading="Admin">
            <CommandItem
              value="admin panel management"
              onSelect={() => runCommand(() => navigate("/admin"))}
            >
              <CogIcon className="h-4 w-4" />
              <span>Go to Admin Panel</span>
            </CommandItem>
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
