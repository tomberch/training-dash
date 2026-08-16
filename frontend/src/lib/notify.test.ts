import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { notify, notifySuccess, notifyError, notifyInfo } from "./notify";
import * as api from "@/api";

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

// Mock API
vi.mock("@/api", () => ({
  createNotification: vi.fn().mockResolvedValue({ id: 1, type: "test", message: "test" }),
}));

describe("notify", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("notify()", () => {
    it("shows success toast and persists to bell", async () => {
      await notify("success", "Test message");

      expect(toast.success).toHaveBeenCalledWith("Test message", undefined);
      expect(api.createNotification).toHaveBeenCalledWith(
        "frontend_success",
        "Test message"
      );
    });

    it("shows error toast and persists to bell", async () => {
      await notify("error", "Error message");

      expect(toast.error).toHaveBeenCalledWith("Error message", undefined);
      expect(api.createNotification).toHaveBeenCalledWith(
        "frontend_error",
        "Error message"
      );
    });

    it("shows info toast and persists to bell", async () => {
      await notify("info", "Info message");

      expect(toast).toHaveBeenCalledWith("Info message", undefined);
      expect(api.createNotification).toHaveBeenCalledWith(
        "frontend_info",
        "Info message"
      );
    });

    it("includes description in toast", async () => {
      await notify("success", "Main message", { description: "Details here" });

      expect(toast.success).toHaveBeenCalledWith("Main message", {
        description: "Details here",
      });
    });

    it("includes description in persisted message", async () => {
      await notify("success", "Main message", { description: "Details here" });

      expect(api.createNotification).toHaveBeenCalledWith(
        "frontend_success",
        "Main message: Details here"
      );
    });

    it("uses custom bellType when provided", async () => {
      await notify("success", "Uploaded", { bellType: "activity_uploaded" });

      expect(api.createNotification).toHaveBeenCalledWith(
        "activity_uploaded",
        "Uploaded"
      );
    });

    it("skips bell when toastOnly is true", async () => {
      await notify("success", "Toast only", { toastOnly: true });

      expect(toast.success).toHaveBeenCalled();
      expect(api.createNotification).not.toHaveBeenCalled();
    });

    it("does not block on API errors", async () => {
      vi.mocked(api.createNotification).mockRejectedValueOnce(new Error("API error"));
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

      // Should not throw
      await notify("success", "Test");

      expect(toast.success).toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to persist notification to bell:",
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe("notifySuccess()", () => {
    it("calls notify with success type", () => {
      notifySuccess("Success!");
      expect(toast.success).toHaveBeenCalledWith("Success!", undefined);
    });
  });

  describe("notifyError()", () => {
    it("calls notify with error type", () => {
      notifyError("Failed!");
      expect(toast.error).toHaveBeenCalledWith("Failed!", undefined);
    });
  });

  describe("notifyInfo()", () => {
    it("calls notify with info type", () => {
      notifyInfo("FYI");
      expect(toast).toHaveBeenCalledWith("FYI", undefined);
    });
  });
});
