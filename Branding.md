# OncoBoard.ai — Frontend Branding

## Identity
- **Product:** OncoBoard.ai
- **Tagline:** From 8 hours to 90 seconds.
- **Tone:** Clear, fast, trustworthy. Google-grade simplicity for life-critical work.

## Color Palette

```css
/* Surfaces */
--color-bg:        #FFFFFF;   /* page */
--color-surface:   #F8F9FA;   /* cards, panels */
--color-surface-2: #E8EAED;   /* elevated sections */
--color-border:    #DADCE0;   /* subtle dividers */

/* Google core */
--color-primary:   #1A73E8;   /* Google Blue — actions, links */
--color-on-primary:#FFFFFF;

/* Semantic accents */
--color-danger:    #EA4335;   /* Google Red — alerts, critical */
--color-success:   #34A853;   /* Google Green — confirmed, done */
--color-warning:   #FBBC04;   /* Google Yellow — pending, needs review */
--color-info:      #1A73E8;   /* same as primary */

/* Text */
--color-text:      #202124;   /* 87% black — Google default */
--color-text-2:    #5F6368;   /* secondary */
--color-text-3:    #80868B;   /* placeholders, disabled */
```

## Typography

```css
--font-sans:  'Google Sans', 'Product Sans', 'Roboto', sans-serif;
--font-mono:  'Roboto Mono', monospace;  /* patient IDs, genomics */

--text-xs:   12px;  --text-sm:  14px;
--text-base: 16px;  --text-lg:  20px;
--text-xl:   24px;  --text-2xl: 32px;

--weight-normal: 400;
--weight-medium: 500;
--weight-bold:   700;
```

## Spacing & Shape

```css
/* Google 8dp grid */
--space-1: 4px;   --space-2: 8px;
--space-3: 16px;  --space-4: 24px;
--space-5: 32px;  --space-6: 48px;

/* Material 3 rounding */
--radius-sm: 8px;
--radius-md: 16px;
--radius-lg: 24px;
--radius-pill: 999px;
```

## Elevation (Material Style)

```css
/* replace heavy borders with shadow layers */
--elevation-1: 0 1px 2px rgba(60,64,67,0.1);
--elevation-2: 0 1px 3px rgba(60,64,67,0.15), 0 4px 8px rgba(60,64,67,0.1);
--elevation-3: 0 1px 6px rgba(60,64,67,0.15), 0 8px 16px rgba(60,64,67,0.1);
```

> Cards and panels float on `--elevation-1`. Right panel / modals use `--elevation-3`.

## Layout
┌──────────────────────────────────────┐
│ Sidebar (240px) │ Main (flex) │
│ Nav │ Topbar (56px) │
│ Agent chips │ Content │
│ │ Right panel │
└──────────────────────────────────────┘

- **Sidebar:** `background: var(--color-surface)`, top logo, bottom agent mini-list
- **Topbar:** `background: var(--color-bg)`, bottom hairline `1px solid var(--color-border)`, search + patient chip
- **Content:** fluid, max-width 1280px, padding `--space-4`
- **Right panel:** 360px, `background: var(--color-surface)`, `box-shadow: var(--elevation-2)`, rounded `--radius-md` on the inner edge

## Vue Structure
src/
assets/tokens.css ← all CSS vars
components/
layout/
AppSidebar.vue
AppTopbar.vue
AppPanel.vue
ui/
BaseSurface.vue ← elevation + radius wrapper
BaseChip.vue ← pill status badges
BaseButton.vue ← filled / tonal / outlined / text
AgentStep.vue ← numbered step indicator
views/
BoardView.vue ← dashboard with agent grid
CaseSummaryView.vue
TrialsView.vue
FollowUpView.vue

## Component Conventions

- **BaseSurface:** `background: var(--color-surface); border-radius: var(--radius-md); box-shadow: var(--elevation-1); padding: var(--space-3);`
- **BaseButton filled:** `background: var(--color-primary); color: var(--color-on-primary); border-radius: var(--radius-pill);`
- **BaseButton tonal:** `background: #D2E3FC; color: #174EA6;` (primary tonal)
- **BaseButton text:** `background: transparent; color: var(--color-primary);` (low emphasis)
- **BaseChip:** `background: var(--color-surface-2); border-radius: var(--radius-pill); padding: 4px 12px; font: var(--text-sm);`
- **AgentStep:** numbered circle + label, connector line when done

## Agent Status

| State   | Style                              |
|---------|------------------------------------|
| Idle    | muted text, outlined chip          |
| Running | primary filled chip + spinner icon |
| Done    | green chip with check icon         |
| Error   | red chip with alert icon             |

> Keep chips compact. OncoBoard runs 7 agents in parallel — horizontal space in the sidebar is precious.

## Icons

- Library: **Material Symbols** (`material-symbols` via Google Fonts or `@material-symbols` npm)
- Weight: 400
- Size: 20px (UI), 24px (navigation), 16px (inline chips)
- Fill: 0 (outlined style) for navigation, 1 (filled) for active states

## Motion

```css
--ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
--ease-emphasized: cubic-bezier(0.2, 0, 0, 1);  /* Material 3 */

--duration-instant: 50ms;
--duration-fast:    150ms;
--duration-normal:  250ms;
```

- Panel reveal: `transform: translateX` + `--ease-emphasized` + `--duration-normal`
- Chip state change: cross-fade `--duration-fast`
- Page transitions: fade `--duration-normal` with slight Y shift
- Hover states: `background` transition `--duration-instant`

## Dark Mode (Optional)

```css
@media (prefers-color-scheme: dark) {
  --color-bg:        #202124;
  --color-surface:   #303134;
  --color-surface-2: #3C4043;
  --color-border:    #5F6368;
  --color-text:      #E8EAED;
  --color-text-2:    #9AA0A6;
}
```

> Google products default to light. Enable dark via system preference only; do not toggle manually in this MVP.

## Don'ts

- No borders where a shadow or gap divider is enough
- No radius below 8px — sharp corners feel non-Google
- No custom icon packs — stick to Material Symbols for consistency
- No text smaller than 12px
- No pure black (`#000`) anywhere
