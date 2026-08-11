import { Component, type ReactNode, type ErrorInfo } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Fallback UI to show when an error occurs */
  fallback?: ReactNode;
  /** Component name for error logging */
  componentName?: string;
  /** Callback when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary component that catches JavaScript errors in child components.
 * Prevents the entire app from crashing when a component fails to render.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const { componentName, onError } = this.props;
    console.error(
      `[ErrorBoundary${componentName ? `: ${componentName}` : ""}] Caught error:`,
      error,
      errorInfo
    );
    onError?.(error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <svg
                className="w-5 h-5 text-red-500 dark:text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-red-800 dark:text-red-300">
                Something went wrong
              </h3>
              <p className="mt-1 text-sm text-red-700 dark:text-red-400">
                {this.props.componentName
                  ? `Failed to render ${this.props.componentName}.`
                  : "This component failed to render."}
              </p>
              <button
                onClick={() => this.setState({ hasError: false, error: null })}
                className="mt-2 text-sm font-medium text-red-600 dark:text-red-400 hover:text-red-500 dark:hover:text-red-300"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Wrapper specifically for chart components with a chart-specific fallback.
 */
interface ChartErrorBoundaryProps {
  children: ReactNode;
  chartName?: string;
  height?: number;
}

export function ChartErrorBoundary({
  children,
  chartName = "Chart",
  height = 200,
}: ChartErrorBoundaryProps) {
  return (
    <ErrorBoundary
      componentName={chartName}
      fallback={
        <div
          className="flex items-center justify-center bg-muted rounded-lg border border-border"
          style={{ height }}
        >
          <div className="text-center p-4">
            <svg
              className="w-8 h-8 text-muted-foreground mx-auto mb-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
            <p className="text-body-secondary">
              Failed to load {chartName.toLowerCase()}
            </p>
          </div>
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  );
}
