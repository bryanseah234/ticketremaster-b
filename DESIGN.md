# TicketRemaster Style Guide

This project uses a dark glassmorphism aesthetic with orange accents.

## Source of Truth

Theme tokens live in `src/config/theme.ts`.
- Update hex/rgba values there to globally re-theme the app.
- Runtime mapping to CSS variables happens in `applyThemeVariables()` from `src/main.ts`.

## CSS Variables

- `--bg`, `--bg-2`: background layers
- `--surface`, `--surface-2`: glass panels/cards
- `--border`: subtle 1px borders
- `--text`, `--muted`: text hierarchy
- `--accent`, `--accent-2`, `--accent-ink`: brand/action colors
- `--success`, `--warning`, `--disabled`: semantic states

## Color Usage

- Backgrounds: `--bg` for the page base, `--bg-2` for depth gradients.
- Glass surfaces: `--surface` for primary cards, `--surface-2` for neutral panels.
- Borders: `--border` for all card and input outlines.
- Text: `--text` for primary copy, `--muted` for secondary copy and hints.
- Accents: `--accent` for primary actions, `--accent-2` for gradients, `--accent-ink` for text on orange.

## Shadows & Blur

- Glass cards use a soft shadow with a large blur radius.
- Backdrop blur is required on `.glass` and `.card` style components to keep the depth look.

## Spacing & Radius

- Page padding: `.page` in `src/assets/main.css` controls global section spacing.
- Grid gaps: `.grid-2`, `.grid-3`, `.grid-4` use consistent 0.8–1rem gaps.
- Radius scale:
  - pills: `999px`
  - controls: `0.75rem`
  - cards/panels: `1rem+`

## Visual Language

- Glass cards: border + blur + soft shadow.
- Toast notifications appear bottom-right for loading and demo-mode states.
- Buttons:
  - Primary = orange gradient
  - Secondary = neutral glass
  - Ghost = transparent + border
- Inputs/select/textarea inherit dark surfaces and border tokens.
- Radius scale:
  - pills: `999px`
  - controls: `0.75rem`
  - cards: `1rem+`

## Typography

- Font stack from `themeConfig.fontFamily`.
- High contrast with muted secondary copy (`--muted`).
- Section titles use `.section-title` sizing and letter-spacing in `src/assets/main.css`.
- Subtitles use `.section-subtitle` with muted color and lower visual weight.

## Layout Patterns

- Page container uses `.page` max-width and padding from `src/assets/main.css`.
- Grid helpers: `.grid-2`, `.grid-3`, `.grid-4`.
- Reusable utility classes:
  - `.glass`
  - `.panel`
  - `.badge`
  - `.small`
- Footer brand block uses stacked tagline lines on desktop and centered layout on mobile.

## Components

- Navbar: translucent glass capsule, centered within max width, orange accent brand.
- Footer: two-column layout on desktop, 2x2 link grid on mobile with centered brand.
- Cards: use `.glass` or `.card` with full-bleed imagery and overlay gradients.
- Toasts: bottom-right stack, click to dismiss, short-lived info states.

## Motion & Interaction

- Buttons lift subtly on hover with a small translate.
- Toasts slide upward on enter and downward on exit.
- Globe uses slow rotation and strong limb lighting for depth.

## Design Preview Route

Visit `/design` to see a live preview of:
- color tokens
- form controls
- button variants
- badges
- typography and panel samples

## Design Preview Route

Visit `/design` to see a live preview of:
- color tokens
- form controls
- button variants
- badges
- typography and panel samples