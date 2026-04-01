# Diagram Maintenance Guide (Mermaid Sequence Diagrams)

Use this folder for scenario diagrams tied to backend workflows.

## Rules
1. Use Mermaid **sequenceDiagram** only.
2. Keep a white background with black text/lines for readability.
3. Keep actor names short and explicit.
4. Avoid overlap by increasing `messageMargin`, `actorMargin`, and fixed `width`.

## Update Workflow
1. Edit `diagrams/scenario_flows.mmd`.
2. Keep each scenario as a separate `sequenceDiagram` block.
3. Validate syntax quickly (copy into Mermaid Live Editor).
4. Render (if `mmdc` is installed):
   - `mmdc -i diagrams/scenario_flows.mmd -o diagrams/scenario_flows.svg -c diagrams/mermaid-render.config.js`
5. Commit both source (`.mmd`) and rendered artifact (`.svg`/`.png`) when generation tooling is available.

## Anti-overlap checklist
- Use `autonumber`.
- Prefer 6 actors or fewer per diagram.
- Split long scenarios into multiple diagrams.
- Keep message text concise and in one line where possible.
