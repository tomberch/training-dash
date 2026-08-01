# 11 — UI styling and polish

**What to build:** Apply a cohesive visual design across the whole app using Tailwind CSS — login, activity list, activity detail (stat tiles, map, charts). Set up Tailwind via `@tailwindcss/vite` and use utility classes throughout for layout, spacing, typography, and color. Make the app responsive and pleasant to use on desktop and tablet. Style the charts (consistent colors, clean axes, readable tooltips) and the map (clean controls, polyline that fits the viewport). No new functionality — this is purely visual polish of existing screens.

**Blocked by:** 01 (tracer-bullet), 02 (charts + toggle), 03 (activity list)

**Status:** done

- [x] Tailwind CSS is set up via `@tailwindcss/vite` and utility classes are used throughout
- [x] Login screen is centered, styled, and readable
- [x] Activity list is a clean table with hover states, proper spacing, and responsive layout
- [x] Activity detail stat tiles are visually grouped (card or grid), not raw inline divs
- [x] Charts have consistent styling — readable axes, clean tooltips, no overflow, consistent height/spacing
- [x] Map has a sensible default zoom that fits the polyline, clean tile layer, no layout issues
- [x] Axis toggle buttons look like toggle buttons, not raw text
- [x] Upload form is styled (file input + feedback state)
- [x] App is usable on tablet-width screens (responsive breakpoints)
- [x] No inline styles — all styling via Tailwind utility classes (except Recharts Tooltip contentStyle which is a library requirement)