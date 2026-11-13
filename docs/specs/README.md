# docs/specs/

Specs for the gated FAQ assistant work. Written from the scope and roadmap document, one spec per roadmap area, and
implemented against the layout in `AGENTS.md`. Each spec splits its changes into **Code** and
**Graph XML**, and labels each claim as observed, documented or unverified.

Current specs:
- [Scope and roadmap](00-scope-and-roadmap.md), [brief](00-brief.md).
- [01: Stop wrong answers](01-stop-wrong-answers.md).
- [02: Registry and trace record](02-registry-and-trace-record.md).
- [03: Graph split, outcome table and DMN](03-graph-split-outcome-table-dmn.md).

The code contains implementations of these phases. Portal imports, shadow comparisons and live acceptance
checks remain deployment work; see each spec's verification sections.
