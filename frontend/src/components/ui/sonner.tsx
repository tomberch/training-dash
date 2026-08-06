import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react"

/**
 * Toast notification component using sonner.
 * Styled to match the Catppuccin theme (latte/mocha).
 * 
 * Usage:
 *   import { toast } from "sonner"
 *   toast.success("Activity uploaded successfully")
 *   toast.error("Failed to sync")
 *   toast("Info message")
 *   toast.success("Activity uploaded", { action: { label: "View", onClick: () => navigate(`/activities/${id}`) } })
 */
const Toaster = ({ ...props }: ToasterProps) => {
  // Detect theme from document attribute (our theming system uses data-theme="latte|mocha")
  const getTheme = (): "light" | "dark" => {
    if (typeof window === "undefined") return "light"
    const theme = document.documentElement.getAttribute("data-theme")
    return theme === "mocha" ? "dark" : "light"
  }

  return (
    <Sonner
      theme={getTheme()}
      className="toaster group"
      position="bottom-right"
      icons={{
        success: <CircleCheckIcon className="size-4 text-success" />,
        info: <InfoIcon className="size-4 text-accent" />,
        warning: <TriangleAlertIcon className="size-4 text-warning" />,
        error: <OctagonXIcon className="size-4 text-danger" />,
        loading: <Loader2Icon className="size-4 animate-spin text-muted-foreground" />,
      }}
      toastOptions={{
        classNames: {
          toast: "group toast bg-surface-elevated border-border text-foreground shadow-lg rounded-lg",
          title: "text-foreground font-medium",
          description: "text-muted-foreground text-sm",
          actionButton: "bg-primary text-primary-foreground hover:bg-primary-hover",
          cancelButton: "bg-muted text-muted-foreground hover:bg-muted/80",
          success: "border-success/20",
          error: "border-danger/20",
          warning: "border-warning/20",
          info: "border-accent/20",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
