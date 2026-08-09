import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary, ChartErrorBoundary } from "./ErrorBoundary";

// Component that throws an error
function ThrowingComponent({ shouldThrow = true }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error("Test error");
  }
  return <div>No error</div>;
}

describe("ErrorBoundary", () => {
  // Suppress console.error for expected errors
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = originalError;
  });

  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <div>Child content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText("Child content")).toBeInTheDocument();
  });

  it("renders default fallback when error occurs", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByText("This component failed to render.")
    ).toBeInTheDocument();
  });

  it("renders custom fallback when provided", () => {
    render(
      <ErrorBoundary fallback={<div>Custom error message</div>}>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText("Custom error message")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("includes component name in error message when provided", () => {
    render(
      <ErrorBoundary componentName="TestComponent">
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(
      screen.getByText("Failed to render TestComponent.")
    ).toBeInTheDocument();
  });

  it("calls onError callback when error occurs", () => {
    const onError = vi.fn();

    render(
      <ErrorBoundary onError={onError}>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({ componentStack: expect.any(String) })
    );
  });

  it("shows Try again button in default fallback", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText("Try again")).toBeInTheDocument();
  });
});

describe("ChartErrorBoundary", () => {
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = originalError;
  });

  it("renders children when no error occurs", () => {
    render(
      <ChartErrorBoundary>
        <div>Chart content</div>
      </ChartErrorBoundary>
    );

    expect(screen.getByText("Chart content")).toBeInTheDocument();
  });

  it("renders chart-specific fallback when error occurs", () => {
    render(
      <ChartErrorBoundary chartName="Power Chart">
        <ThrowingComponent />
      </ChartErrorBoundary>
    );

    expect(screen.getByText("Failed to load power chart")).toBeInTheDocument();
  });

  it("uses default chart name when not provided", () => {
    render(
      <ChartErrorBoundary>
        <ThrowingComponent />
      </ChartErrorBoundary>
    );

    expect(screen.getByText("Failed to load chart")).toBeInTheDocument();
  });
});
