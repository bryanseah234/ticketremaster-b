# Diagram Source Guide

This folder now uses **Mermaid `.mmd` files as the source of truth** for maintained diagrams.

## What lives here

- `01_...mmd` to `12_...mmd`: source files for the numbered PNG gallery
- `readme_*.mmd`, `frontend_gateway_flow.mmd`, `notification_realtime_flow.mmd`: source files for README-facing SVG diagrams
- `.png` and `.svg` files: rendered artifacts for GitHub/docs/slides
- `.uml` files: legacy breadcrumbs only; they are no longer the maintained source format

## Editing rules

1. Prefer Mermaid for all new or updated diagrams.
2. Keep labels short and explicit.
3. Use `sequenceDiagram` for workflows and `flowchart LR` for architecture views.
4. Keep diagrams honest to the current code, routes, and runtime.

## Regeneration

Render a single source file:

```powershell
mmdc -i diagrams/01_ticket_purchase_happy_path.mmd -o diagrams/01_ticket_purchase_happy_path.png -c diagrams/mermaid-render.config.js
```

Render a README SVG:

```powershell
mmdc -i diagrams/readme_system_architecture.mmd -o diagrams/readme_system_architecture.svg -c diagrams/mermaid-render.config.js
```

## Maintenance note

If a rendered PNG or SVG changes, commit both:

- the `.mmd` source
- the generated `.png` or `.svg`

That keeps the folder auditable and easy to update later.
