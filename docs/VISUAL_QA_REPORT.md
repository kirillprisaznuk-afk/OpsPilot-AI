# Stage 7 rendered visual QA

The production UI was inspected in Edge. The dashboard used real KPIs and coherent visual hierarchy across desktop, tablet and mobile. The historical views showed the actual date at the top. Procurement, inventory and fulfilment separated the trend from exact source observations. On an August-only chart, the single observation is a point rather than a fabricated trend. The dashboard uses distinct cards for historical numbers and current workflows.

The finance review found a dead end after viewing a supplier's recorded exposure. The comparison table now links attributed suppliers to their existing records and has real pagination. It preserves the historical period. Opening the data table grows the grid row, creating extra white space alongside the chart. At mobile sizes, dense tables still use contained horizontal scrolling.

The sign-in capture contains empty fields. Approval shows the exact evidence, requested change and independent review action. The receipt capture is centered on the committed result and links to the affected task and audit. The source capture shows the procurement passage, version and checksum. Workflow notes containing markup are visually literal.

Playwright exercised keyboard Space and Enter in the approval dialog, checked focus on entry, and measured document width at 1440, 1280, 1024, 768 and 390 px. The loaded desktop dashboard, loaded mobile task list and loaded admin settings were scanned with axe WCAG A/AA tags. These are targeted checks. The mobile native department filter can truncate its closed label, and the menu retains the full label. The broad shell, contrast, visible focus and motion preference support were inspected without assigning a numerical design grade.

Selected captures are in [the screenshot directory](../reports/stage7-screenshots/). The main browser report retains tested widths and axe findings. [Browser evidence](../reports/stage7-browser.json)
