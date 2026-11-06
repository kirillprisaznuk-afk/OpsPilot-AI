# OpsPilot design system

OpsPilot uses a compact indigo symbol and wordmark, quiet white surfaces, a cool neutral canvas, a fixed desktop rail and a responsive mobile drawer. The design centers on an executive dashboard and a deliberate approval workspace. Use smaller supporting surfaces selectively: one joined KPI strip, a wide chart, a vertical exception list, and clear tables with exact values.

| Token | Use |
|---|---|
| Ink `#1c2538` | Hierarchy, record names and numerical values |
| Accent `#4955d8` | Primary actions, navigation selection and key series |
| Surface `#ffffff` / canvas `#f6f7fa` | Working panels and visual separation |
| Border `#e6e8ed` | Quiet division, table and form structure |
| Muted ink `#626d82` | Supporting labels with contrast correction |
| Teal / amber / red | Confirmed/attention/denied states, paired with text |

Segoe UI, with Inter when already present and Arial fallback, keeps startup offline and avoids redistributing restricted font files. The typical title is 29 px desktop, 25 px narrow, with compact section headers and tabular KPI numerals. Panels use 10 px radii; buttons/inputs 6–7 px. Focus rings are visible; reduced-motion preference disables transitions. Table overflow stays inside the table container.

Shared primitives: `PageHeading`, `Panel`, `Status`, `Kpi`, `Field`, `Modal`, `Pagination`, loading/empty/error states, evidence notes and chart components. Radix Dialog supplies focus trapping and Escape. All charts show actual backend numbers and provide expandable exact-value tables. No colour-only status signal, arbitrary trend, or fabricated comparison is used.

The first rendered review exposed insufficient muted contrast and an accessible-name mismatch on the account control. Those issues were corrected before the final screenshots; see the visual review for measured outcomes and remaining limits.
