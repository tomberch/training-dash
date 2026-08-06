# TrainDash Design System

This document is the canonical reference for TrainDash's visual design system. It covers color tokens, typography, spacing, components, and theming.

## Themes

TrainDash uses the [Catppuccin](https://catppuccin.com/) color palette with two themes:

- **Latte** (light) — Default theme, warm and readable
- **Mocha** (dark) — High contrast dark theme

Themes are applied via the `data-theme` attribute on `<html>`:
```html
<html data-theme="latte">  <!-- Light mode -->
<html data-theme="mocha">  <!-- Dark mode -->
```

Theme initialization happens in `App.tsx` and respects:
1. User's stored preference in `localStorage` (`traindash-theme`)
2. System preference via `prefers-color-scheme`
3. Fallback to Latte (light)

### Adding New Themes

To add a new theme (e.g., Catppuccin Frappé):
1. Create `src/themes/frappe.css` following the pattern in `latte.css`
2. Import it in `src/index.css`
3. Map all semantic tokens to the new palette colors
4. Update the theme switcher UI to include the new option

## Color Tokens

### Semantic Tokens (Use These)

Always use semantic tokens instead of raw colors. These automatically adapt to the active theme.

| Token | Light (Latte) | Dark (Mocha) | Usage |
|-------|---------------|--------------|-------|
| `bg-background` | `#eff1f5` | `#1e1e2e` | Page background |
| `bg-card` | `#ffffff` | `#181825` | Card/panel backgrounds |
| `bg-muted` | `#e6e9ef` | `#313244` | Secondary backgrounds, disabled states |
| `text-foreground` | `#4c4f69` | `#cdd6f4` | Primary text |
| `text-muted-foreground` | `#6c6f85` | `#a6adc8` | Secondary/helper text |
| `border-border` | `#ccd0da` | `#45475a` | Default borders |
| `bg-primary` | `#8839ef` | `#cba6f7` | Primary actions, brand |
| `text-primary` | `#8839ef` | `#cba6f7` | Primary text/links |
| `bg-success` | `#40a02b` | `#a6e3a1` | Success states |
| `text-success` | `#40a02b` | `#a6e3a1` | Success text |
| `bg-destructive` | `#d20f39` | `#f38ba8` | Danger/delete actions |
| `text-destructive` | `#d20f39` | `#f38ba8` | Error text |
| `bg-warning` | `#df8e1d` | `#f9e2af` | Warning states |

### Chart Colors (Fixed, Not Themeable)

Chart colors have domain-specific meaning and stay consistent across themes:

```css
/* PMC Chart */
--color-chart-ctl: #3b82f6;    /* blue - Chronic Training Load */
--color-chart-atl: #ec4899;    /* pink - Acute Training Load */
--color-chart-tsb: #f59e0b;    /* amber - Training Stress Balance */

/* Power Zones (Z1-Z7) */
--color-zone-1: #9ca3af;       /* gray - Recovery */
--color-zone-2: #3b82f6;       /* blue - Endurance */
--color-zone-3: #22c55e;       /* green - Tempo */
--color-zone-4: #eab308;       /* yellow - Threshold */
--color-zone-5: #f97316;       /* orange - VO2max */
--color-zone-6: #ef4444;       /* red - Anaerobic */
--color-zone-7: #8b5cf6;       /* violet - Neuromuscular */

/* Activity Series */
--color-series-power: #f59e0b;    /* amber */
--color-series-hr: #ef4444;       /* red */
--color-series-speed: #3b82f6;    /* blue */
--color-series-cadence: #8b5cf6;  /* violet */
--color-series-elevation: #10b981; /* emerald */
```

## Typography

TrainDash uses the system font stack for optimal performance and native feel:

```css
font-family: system-ui, -apple-system, sans-serif;
```

### Scale

| Class | Size | Usage |
|-------|------|-------|
| `text-xs` | 0.75rem | Labels, badges, helper text |
| `text-sm` | 0.875rem | Body text, form inputs |
| `text-base` | 1rem | Default body |
| `text-lg` | 1.125rem | Section headings |
| `text-xl` | 1.25rem | Card titles |
| `text-2xl` | 1.5rem | Page headings |

### Font Weights

- `font-normal` (400) — Body text
- `font-medium` (500) — Labels, buttons, emphasis
- `font-semibold` (600) — Headings, important values
- `font-bold` (700) — Page titles, metrics

## Spacing

Use Tailwind's spacing scale consistently:

| Token | Value | Usage |
|-------|-------|-------|
| `gap-1` | 0.25rem | Tight inline spacing |
| `gap-2` | 0.5rem | Related elements |
| `gap-3` | 0.75rem | Form field spacing |
| `gap-4` | 1rem | Section padding |
| `gap-6` | 1.5rem | Card/section margins |

### Common Patterns

- Card padding: `p-4` or `p-6`
- Form field spacing: `space-y-3` or `space-y-4`
- Section spacing: `space-y-6`
- Page margins: `px-4 py-6`

## Border Radius

```css
--radius: 0.5rem;  /* 8px - base radius */
```

| Class | Usage |
|-------|-------|
| `rounded-lg` | Cards, buttons, inputs |
| `rounded-xl` | Large cards, dialogs |
| `rounded-full` | Avatars, badges |

## Components

TrainDash uses [shadcn/ui](https://ui.shadcn.com/) components built on Radix primitives.

### Available Components

| Component | Import | Usage |
|-----------|--------|-------|
| `Button` | `@/components/ui/button` | Actions, form submissions |
| `Input` | `@/components/ui/input` | Text inputs, form fields |
| `Label` | `@/components/ui/label` | Form labels |
| `Card` | `@/components/ui/card` | Content containers |
| `Avatar` | `@/components/ui/avatar` | User avatars |
| `Dialog` | `@/components/ui/dialog` | Modal dialogs |
| `Skeleton` | `@/components/ui/skeleton` | Loading placeholders |

### Button Variants

```tsx
import { Button } from "@/components/ui/button";

<Button>Primary action</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="destructive">Delete</Button>
<Button variant="link">Link style</Button>
```

### Button Sizes

```tsx
<Button size="xs">Extra small</Button>
<Button size="sm">Small</Button>
<Button size="default">Default</Button>
<Button size="lg">Large</Button>
<Button size="icon">Icon only</Button>
```

### Card Pattern

```tsx
import { Card, CardHeader, CardTitle, CardContent, CardAction } from "@/components/ui/card";

<Card>
  <CardHeader>
    <CardTitle>Section Title</CardTitle>
    <CardAction>
      <Button variant="ghost" size="sm">Action</Button>
    </CardAction>
  </CardHeader>
  <CardContent className="space-y-4">
    {/* Content */}
  </CardContent>
</Card>
```

### Form Pattern

```tsx
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

<div className="space-y-1.5">
  <Label>Field Name</Label>
  <Input type="text" placeholder="Enter value" />
  <p className="text-xs text-muted-foreground">Helper text</p>
</div>
```

### Feedback Alert Pattern

For success/error feedback messages:

```tsx
<div className={cn(
  "p-3 rounded-lg text-sm border",
  type === "success"
    ? "bg-success/10 text-success border-success/20"
    : "bg-destructive/10 text-destructive border-destructive/20"
)}>
  {message}
</div>
```

### Loading States

```tsx
// Skeleton placeholders
<div className="animate-pulse">
  <div className="h-5 bg-muted rounded w-1/4 mb-4"></div>
  <div className="h-20 bg-muted rounded"></div>
</div>

// Or use Skeleton component
import { Skeleton } from "@/components/ui/skeleton";
<Skeleton className="h-5 w-1/4" />
```

### Status Badges

```tsx
// Connected/success
<span className="px-2 py-1 text-xs font-medium rounded-full bg-success/20 text-success">
  Connected
</span>

// Disconnected/neutral
<span className="px-2 py-1 text-xs font-medium rounded-full bg-muted text-muted-foreground">
  Not configured
</span>
```

### Toast Notifications

TrainDash uses [Sonner](https://sonner.emilkowal.ski/) for toast notifications. The `<Toaster>` component is mounted in `App.tsx` and responds to theme changes via the `data-theme` attribute.

```tsx
import { toast } from "sonner";

// Success toast with action
toast.success("Activity uploaded successfully", {
  action: {
    label: "View",
    onClick: () => navigate(`/activities/${activityId}`),
  },
});

// Error toast with description
toast.error("Upload failed", {
  description: error.message,
});

// Simple info toast
toast("Processing complete");

// Promise-based toast (shows loading, then success/error)
toast.promise(asyncOperation(), {
  loading: "Processing...",
  success: "Done!",
  error: "Failed",
});
```

**Configuration:** Toasts appear in the bottom-right corner with a maximum of 4 visible. Auto-dismiss after 4 seconds for success/info, errors persist until dismissed.

**Styling:** Toasts automatically adapt to the current theme (Latte/Mocha) using semantic colors:
- Success: `text-success` (green)
- Error: `text-destructive` (red)
- Warning: `text-warning` (amber)

### Empty States

Use the `EmptyState` component for sections with no data.

```tsx
import { EmptyState } from "@/components/ui/empty-state";

<EmptyState
  icon={
    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  }
  title="No power data available"
  description="Upload activities with power data to see your power curve and track improvements over time."
  action={<Button onClick={handleUpload}>Upload Activity</Button>}
/>
```

**Tone Guidelines:**
- **Title:** Neutral, factual — e.g., "No activities yet", "No data for this range"
- **Description:** Helpful direction on resolution — e.g., "Upload a FIT file or connect Xert..."
- **Icon:** Simple monochrome SVG in `text-muted-foreground`
- **Action:** Optional button for primary resolution

**When to add a button CTA:**
- New user onboarding (Dashboard) — yes, guided cards
- Filtered results showing zero — no, just description
- Missing data (power curve, PMC) — no, just description

## Migration Guide

When migrating existing components:

1. **Replace raw colors with semantic tokens:**
   - `text-gray-900 dark:text-white` → `text-foreground`
   - `text-gray-500 dark:text-gray-400` → `text-muted-foreground`
   - `bg-white dark:bg-gray-800` → `bg-card`
   - `border-gray-200 dark:border-gray-700` → `border-border`
   - `bg-indigo-600` → `bg-primary`
   - `text-red-600` → `text-destructive`
   - `bg-green-100 text-green-700` → `bg-success/10 text-success`

2. **Remove all `dark:` variants** — themes handle this automatically

3. **Replace raw HTML elements with shadcn components:**
   - `<input>` → `<Input>`
   - `<label>` → `<Label>`
   - `<button>` → `<Button>`
   - Section containers → `<Card>` with `CardHeader`/`CardContent`

4. **Use the `cn()` utility** for conditional classes:
   ```tsx
   import { cn } from "@/lib/utils";
   
   <div className={cn(
     "base-classes",
     condition && "conditional-classes"
   )} />
   ```

## Files Reference

| File | Purpose |
|------|---------|
| `src/index.css` | Token contract, chart colors, base styles |
| `src/themes/latte.css` | Light theme token values |
| `src/themes/mocha.css` | Dark theme token values |
| `src/components/ui/*.tsx` | shadcn/ui components |
| `src/components/ui/sonner.tsx` | Toast notification component |
| `src/lib/utils.ts` | `cn()` utility for class merging |
| `src/hooks/useTheme.ts` | Theme switching hook |
