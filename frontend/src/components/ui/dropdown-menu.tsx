import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

interface DropdownMenuProps {
  children: React.ReactNode;
}

interface DropdownMenuTriggerProps {
  children: React.ReactNode;
  asChild?: boolean;
}

interface DropdownMenuContentProps {
  children: React.ReactNode;
  align?: "start" | "center" | "end";
  className?: string;
}

interface DropdownMenuItemProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
}

interface DropdownMenuSeparatorProps {
  className?: string;
}

const DropdownMenuContext = React.createContext<{
  open: boolean;
  setOpen: (open: boolean) => void;
  triggerRef: React.RefObject<HTMLDivElement | null>;
}>({ open: false, setOpen: () => {}, triggerRef: { current: null } });

export function DropdownMenu({ children }: DropdownMenuProps) {
  const [open, setOpen] = React.useState(false);
  const triggerRef = React.useRef<HTMLDivElement>(null);

  // Close on escape
  React.useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }
  }, [open]);

  // Close on click outside
  React.useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-dropdown-menu]") && !target.closest("[data-dropdown-content]")) {
        setOpen(false);
      }
    }
    if (open) {
      // Delay to avoid closing immediately on the same click that opened
      const timer = setTimeout(() => {
        document.addEventListener("click", handleClickOutside);
      }, 0);
      return () => {
        clearTimeout(timer);
        document.removeEventListener("click", handleClickOutside);
      };
    }
  }, [open]);

  return (
    <DropdownMenuContext.Provider value={{ open, setOpen, triggerRef }}>
      <div ref={triggerRef} className="relative inline-block" data-dropdown-menu>
        {children}
      </div>
    </DropdownMenuContext.Provider>
  );
}

export function DropdownMenuTrigger({ children, asChild }: DropdownMenuTriggerProps) {
  const { open, setOpen } = React.useContext(DropdownMenuContext);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setOpen(!open);
  };

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<{ onClick?: (e: React.MouseEvent) => void }>, {
      onClick: handleClick,
    });
  }

  return (
    <button type="button" onClick={handleClick}>
      {children}
    </button>
  );
}

export function DropdownMenuContent({ children, align = "end", className }: DropdownMenuContentProps) {
  const { open, triggerRef } = React.useContext(DropdownMenuContext);
  const [position, setPosition] = React.useState({ top: 0, left: 0, right: 0 });

  React.useEffect(() => {
    if (open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPosition({
        top: rect.bottom + window.scrollY + 4, // 4px gap
        left: rect.left + window.scrollX,
        right: window.innerWidth - rect.right + window.scrollX,
      });
    }
  }, [open, triggerRef]);

  if (!open) return null;

  const content = (
    <div
      data-dropdown-content
      style={{
        position: "absolute",
        top: position.top,
        ...(align === "end" ? { right: position.right } : { left: position.left }),
      }}
      className={cn(
        "z-[9999] min-w-[160px] py-1 bg-popover border border-border rounded-lg shadow-lg",
        className
      )}
    >
      {children}
    </div>
  );

  return createPortal(content, document.body);
}

export function DropdownMenuItem({ children, onClick, disabled, className }: DropdownMenuItemProps) {
  const { setOpen } = React.useContext(DropdownMenuContext);

  const handleClick = () => {
    if (disabled) return;
    onClick?.();
    setOpen(false);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      className={cn(
        "w-full px-3 py-2 text-sm text-left flex items-center gap-2",
        "hover:bg-muted transition-colors",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
    >
      {children}
    </button>
  );
}

export function DropdownMenuSeparator({ className }: DropdownMenuSeparatorProps) {
  return <div className={cn("h-px my-1 bg-border", className)} />;
}
