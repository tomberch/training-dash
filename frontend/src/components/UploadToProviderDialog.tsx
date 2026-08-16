import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  fetchFitDevices,
  uploadToProvider,
  fetchMyXertCredentials,
  fetchMyGarminCredentials,
  type FitDevice,
  type UploadToProviderRequest,
} from "@/api";

// Storage key for last used device
const LAST_DEVICE_KEY = "trainingdash:lastUploadDevice";

interface UploadToProviderDialogProps {
  activityId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type Provider = "xert" | "garmin";

export function UploadToProviderDialog({
  activityId,
  open,
  onOpenChange,
}: UploadToProviderDialogProps) {
  const [provider, setProvider] = React.useState<Provider | null>(null);
  const [connectedProviders, setConnectedProviders] = React.useState<Provider[]>([]);
  const [providersLoading, setProvidersLoading] = React.useState(true);
  const [devices, setDevices] = React.useState<FitDevice[]>([]);
  const [devicesLoading, setDevicesLoading] = React.useState(false);
  const [selectedDevice, setSelectedDevice] = React.useState<FitDevice | null>(null);
  const [deviceSearch, setDeviceSearch] = React.useState("");
  const [showDeviceDropdown, setShowDeviceDropdown] = React.useState(false);
  const [isUploading, setIsUploading] = React.useState(false);

  const deviceInputRef = React.useRef<HTMLInputElement>(null);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  // Load connected providers on open
  React.useEffect(() => {
    if (open) {
      loadConnectedProviders();
    }
  }, [open]);

  async function loadConnectedProviders() {
    setProvidersLoading(true);
    try {
      const [xertStatus, garminStatus] = await Promise.all([
        fetchMyXertCredentials().catch(() => ({ configured: false })),
        fetchMyGarminCredentials().catch(() => ({ configured: false })),
      ]);
      
      const connected: Provider[] = [];
      if (garminStatus.configured) connected.push("garmin");
      if (xertStatus.configured) connected.push("xert");
      
      setConnectedProviders(connected);
      // Auto-select first connected provider
      if (connected.length > 0 && !provider) {
        setProvider(connected[0]);
      }
    } catch {
      toast.error("Failed to load provider status");
    } finally {
      setProvidersLoading(false);
    }
  }

  // Load devices on mount
  React.useEffect(() => {
    if (open && devices.length === 0) {
      loadDevices();
    }
  }, [open, devices.length]);

  // Load last used device from localStorage
  React.useEffect(() => {
    if (open && devices.length > 0 && !selectedDevice) {
      const lastDeviceId = localStorage.getItem(LAST_DEVICE_KEY);
      if (lastDeviceId) {
        const device = devices.find((d) => d.id === parseInt(lastDeviceId, 10));
        if (device) {
          setSelectedDevice(device);
          setDeviceSearch(device.display_name);
        }
      }
    }
  }, [open, devices, selectedDevice]);

  // Close dropdown on click outside
  React.useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        deviceInputRef.current &&
        !deviceInputRef.current.contains(e.target as Node)
      ) {
        setShowDeviceDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function loadDevices() {
    setDevicesLoading(true);
    try {
      const response = await fetchFitDevices();
      setDevices(response.devices);
    } catch {
      toast.error("Failed to load device list");
    } finally {
      setDevicesLoading(false);
    }
  }

  // Filter devices based on search
  const filteredDevices = React.useMemo(() => {
    if (!deviceSearch.trim()) {
      // Show popular devices when no search
      const popularIds = [4062, 3843, 3121, 2713, 3570]; // Edge 840, 1040, 530, 1030, 1030 Plus
      const popular = devices.filter((d) => popularIds.includes(d.id));
      const rest = devices.filter((d) => !popularIds.includes(d.id)).slice(0, 10);
      return [...popular, ...rest];
    }
    const search = deviceSearch.toLowerCase();
    return devices
      .filter(
        (d) =>
          d.display_name.toLowerCase().includes(search) ||
          d.name.toLowerCase().includes(search)
      )
      .slice(0, 20);
  }, [devices, deviceSearch]);

  function handleDeviceSelect(device: FitDevice) {
    setSelectedDevice(device);
    setDeviceSearch(device.display_name);
    setShowDeviceDropdown(false);
    // Save to localStorage
    localStorage.setItem(LAST_DEVICE_KEY, device.id.toString());
  }

  function handleClearDevice() {
    setSelectedDevice(null);
    setDeviceSearch("");
    localStorage.removeItem(LAST_DEVICE_KEY);
  }

  async function handleUpload() {
    if (!provider) return;
    setIsUploading(true);
    try {
      const request: UploadToProviderRequest = {
        provider,
        device_product_id: selectedDevice?.id ?? null,
      };
      const result = await uploadToProvider(activityId, request);
      toast.success(
        `Uploaded to ${provider === "garmin" ? "Garmin Connect" : "Xert"} (ID: ${result.provider_activity_id})`
      );
      onOpenChange(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload to Provider</DialogTitle>
          <DialogDescription>
            Upload this activity to an external service. Optionally change the
            device type to unlock platform-specific features.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Provider selection */}
          <div className="space-y-2">
            <Label>Provider</Label>
            {providersLoading ? (
              <div className="flex gap-2">
                <div className="flex-1 h-10 bg-muted animate-pulse rounded-lg" />
                <div className="flex-1 h-10 bg-muted animate-pulse rounded-lg" />
              </div>
            ) : connectedProviders.length === 0 ? (
              <p className="text-body-secondary py-4 text-center">
                No providers connected. Connect Garmin or Xert in{" "}
                <a href="/settings" className="text-primary hover:underline">
                  Settings
                </a>{" "}
                to upload activities.
              </p>
            ) : (
              <div className="flex gap-3">
                {connectedProviders.includes("garmin") && (
                  <button
                    type="button"
                    onClick={() => setProvider("garmin")}
                    className={`flex-1 px-4 py-3 rounded-lg border-2 font-medium transition ${
                      provider === "garmin"
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-card text-foreground border-border hover:border-primary/50 hover:bg-muted"
                    }`}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <svg
                        className="w-5 h-5"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                      >
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
                      </svg>
                      Garmin Connect
                    </div>
                  </button>
                )}
                {connectedProviders.includes("xert") && (
                  <button
                    type="button"
                    onClick={() => setProvider("xert")}
                    className={`flex-1 px-4 py-3 rounded-lg border-2 font-medium transition ${
                      provider === "xert"
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-card text-foreground border-border hover:border-primary/50 hover:bg-muted"
                    }`}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <svg
                        className="w-5 h-5"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                      >
                        <path d="M13 3L4 14h7l-1 7 9-11h-7l1-7z" />
                      </svg>
                      Xert
                    </div>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Device selection (optional) */}
          <div className="space-y-2">
            <Label>
              Device Type{" "}
              <span className="text-muted-foreground font-normal">
                (optional)
              </span>
            </Label>
            <p className="text-caption">
              Change the device to unlock platform-specific features (e.g.,
              Garmin Cycling Dynamics).
            </p>
            <div className="relative">
              <Input
                ref={deviceInputRef}
                type="text"
                placeholder={
                  devicesLoading ? "Loading devices..." : "Search devices..."
                }
                value={deviceSearch}
                onChange={(e) => {
                  setDeviceSearch(e.target.value);
                  setSelectedDevice(null);
                  setShowDeviceDropdown(true);
                }}
                onFocus={() => setShowDeviceDropdown(true)}
                disabled={devicesLoading}
              />
              {selectedDevice && (
                <button
                  type="button"
                  onClick={handleClearDevice}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              )}
              {showDeviceDropdown && filteredDevices.length > 0 && (
                <div
                  ref={dropdownRef}
                  className="absolute z-50 w-full mt-1 max-h-48 overflow-auto bg-popover border border-border rounded-lg shadow-lg"
                >
                  {filteredDevices.map((device) => (
                    <button
                      key={device.id}
                      type="button"
                      onClick={() => handleDeviceSelect(device)}
                      className={`w-full px-3 py-2 text-left text-body hover:bg-muted transition ${
                        selectedDevice?.id === device.id
                          ? "bg-muted font-medium"
                          : ""
                      }`}
                    >
                      {device.display_name}
                      <span className="text-muted-foreground ml-2 text-caption">
                        ({device.id})
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {selectedDevice && (
              <p className="text-caption text-success">
                Selected: {selectedDevice.display_name} (ID: {selectedDevice.id})
              </p>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={isUploading || !provider || connectedProviders.length === 0}>
            {isUploading ? (
              <>
                <svg
                  className="w-4 h-4 mr-2 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="text-primary/25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="text-primary-foreground"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Uploading...
              </>
            ) : (
              <>
                <svg
                  className="w-4 h-4 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                Upload
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
