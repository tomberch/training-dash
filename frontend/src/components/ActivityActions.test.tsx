import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ActivityActions } from "./ActivityActions";

describe("ActivityActions", () => {
  const defaultProps = {
    onUploadToProvider: vi.fn(),
    onExportFit: vi.fn(),
  };

  it("renders Actions button", () => {
    render(<ActivityActions {...defaultProps} />);
    expect(screen.getByRole("button", { name: /actions/i })).toBeInTheDocument();
  });

  it("shows dropdown menu when clicked", async () => {
    const user = userEvent.setup();
    render(<ActivityActions {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    expect(screen.getByText("Export FIT File")).toBeInTheDocument();
  });

  it("shows Upload to Provider when hasConnectedProviders is true (default)", async () => {
    const user = userEvent.setup();
    render(<ActivityActions {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    expect(screen.getByText("Upload to Provider")).toBeInTheDocument();
    expect(screen.getByText("Export FIT File")).toBeInTheDocument();
  });

  it("hides Upload to Provider when hasConnectedProviders is false", async () => {
    const user = userEvent.setup();
    render(<ActivityActions {...defaultProps} hasConnectedProviders={false} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    expect(screen.queryByText("Upload to Provider")).not.toBeInTheDocument();
    expect(screen.getByText("Export FIT File")).toBeInTheDocument();
  });

  it("calls onUploadToProvider when Upload to Provider is clicked", async () => {
    const onUploadToProvider = vi.fn();
    const user = userEvent.setup();
    render(
      <ActivityActions
        {...defaultProps}
        onUploadToProvider={onUploadToProvider}
      />
    );

    await user.click(screen.getByRole("button", { name: /actions/i }));
    await user.click(screen.getByText("Upload to Provider"));

    expect(onUploadToProvider).toHaveBeenCalledTimes(1);
  });

  it("calls onExportFit when Export FIT File is clicked", async () => {
    const onExportFit = vi.fn();
    const user = userEvent.setup();
    render(<ActivityActions {...defaultProps} onExportFit={onExportFit} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));
    await user.click(screen.getByText("Export FIT File"));

    expect(onExportFit).toHaveBeenCalledTimes(1);
  });

  it("always shows Export FIT File regardless of provider status", async () => {
    const user = userEvent.setup();
    
    // Test with providers
    const { unmount } = render(<ActivityActions {...defaultProps} hasConnectedProviders={true} />);
    await user.click(screen.getByRole("button", { name: /actions/i }));
    expect(screen.getByText("Export FIT File")).toBeInTheDocument();
    unmount();

    // Test without providers
    render(<ActivityActions {...defaultProps} hasConnectedProviders={false} />);
    await user.click(screen.getByRole("button", { name: /actions/i }));
    expect(screen.getByText("Export FIT File")).toBeInTheDocument();
  });
});
