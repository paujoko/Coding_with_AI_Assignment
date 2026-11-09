# 0003 PlantUML as the diagram notation

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5)

## Decision

Diagrams are stored as PlantUML source and rendered to SVG by the backend through a `DiagramRenderer` port (local `plantuml.jar` or a PlantUML server). Without a renderer the UI shows the source.

## Why

- The project requirements name use case, class, sequence, activity, component and deployment diagrams. PlantUML supports all of them; Mermaid has no use case diagram.
- Text notation: agents read and write it, git diffs it, the developer edits it.
- The course UML lecture uses UML proper (draw.io); PlantUML is closer to that than Mermaid's flowchart-based workarounds.

## Alternatives

- Mermaid: renders in the browser without Java, but no use case or deployment diagrams.
- draw.io XML: what the lecture used, but verbose and hard for an LLM to keep consistent.

## Consequences

- Rendering needs Java plus `plantuml.jar`, or a PlantUML server (Docker image `plantuml/plantuml-server`). Not set up yet.
- Drift detection needs a PlantUML class-diagram parser (subset), to be written for P7.
