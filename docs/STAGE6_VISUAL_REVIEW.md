# Stage 6 rendered design review

The review used the real OpsPilot Compose application, the local sign-in page, and Edge captures of authenticated views with synthetic PostgreSQL records. It examined rendered states, including loaded content, verified evidence, an approved workflow, the resulting receipt, and a narrow task list. Screenshots in [the evidence directory](../reports/stage6-screenshots/) are from the browser suite. This is a design review with targeted accessibility checks, not a full WCAG conformance audit.

| Category | Observed issue, correction, or remaining tradeoff |
|---|---|
| 01. Visual hierarchy | On the dashboard, a date range and the KPI strip establish scope before the trend and exception panels. Small muted explanatory copy was too faint in the first review; strengthened the supporting ink. |
| 02. Typography | KPI numbers are aligned using tabular figures, and the reporting dates read separately from the page title. Wrapped headings and long option names needed more room; adjusted the narrow layout and preserved the full option text. |
| 03. Spacing consistency | The loaded approval and receipt views separate evidence, decision and audit details into distinct sections. Narrow views trade some whitespace for larger usable controls; table headers stay aligned with the data. |
| 04. Colour discipline | Indigo marks navigation and primary actions; status is always named. Axe measured 3.94:1 on three desktop amber values against white, so the amber text token changed to `#965b12`. A low-contrast mobile account badge was darkened separately. |
| 05. Dashboard composition | The 1440 px capture shows the KPI strip, delivery trend, exception stack and domain links without competing calls to action. Below tablet width the panels stack, so the lower modules require scrolling. |
| 06. Data visualisation quality | The measured series has tooltips and an expandable exact-value table. The chart communicates the direction and the table supplies precise values; no invented trend or inferred target is shown. |
| 07. Table usability | Searchable, paged tables show source scope and use aligned figures. Wide tables scroll inside their own region on mobile. At 390 px the native department selector truncates the closed label visually; the full label is available in its menu and accessible name. |
| 08. Navigation clarity | The desktop rail groups business, knowledge and governance routes. The mobile drawer closes after selection and the account control names its action. The citation view has a specific Knowledge library return link; its top-level breadcrumb remains generic. There is no global cross-domain search. |
| 09. Workflow interaction quality | Draft, submission, approval and execution have separate actions. A false empty evidence state during loading was replaced by a visible loading state; the final review makes absence of evidence distinct from loading. |
| 10. Approval review clarity | Review shows the actual action, target, scope, captured evidence and allowed choices. The execute step is separate. Rejecting, expiry and stale evidence leave distinct outcomes rather than a generic confirmation. |
| 11. Evidence readability | Source identifiers and excerpts are readable plain text. The citation links to the exact source version; opening a long source still requires scrolling the document. |
| 12. Responsive layout | The dashboard was rendered at 1440, 1280, 1024, 768 and 390 CSS pixels. The loaded mobile task list was reviewed separately. Dense administrative tables retain contained horizontal scrolling. |
| 13. Accessibility | Fixed contrast and accessible-name issues surfaced by axe. Keyboard coverage includes moving into the review dialog, using Space and Enter, and returning focus. This does not substitute for manual assistive technology testing. |
| 14. Overall visual coherence | Shared type, spacing, status and evidence styles carry from dashboard to suppliers, knowledge, Copilot and approval. The evidence-heavy pages necessarily have more visual density than the overview. |
| 15. Professional commercial appearance | The sign-in screen and workspace use the same identity, typography and controls; the dashboard supports drill-down to operating records, not marketing content. A single local workspace and restrained typography fit this release. |

Initial attempts and corrections are recorded in the [acceptance report](STAGE6_REPORT.md). The scope of the automated scan and the measured viewport widths are recorded in the [browser evidence](../reports/stage6-browser.json).
