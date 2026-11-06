# Demonstrate OpsPilot in five minutes

Use the local installation or an isolated demo checkout. Open the generated accounts file in your editor. You will need `stage5.operator` and `stage5.reviewer`. Keep the file off screen during the walkthrough. [Setup and credentials](QUICK_START.md)

| Time | Show | Explain |
|---|---|---|
| 0:00–0:45 | Sign in as the operator. Open **Operations overview**. | Northstar Supply is a synthetic distributor. This dashboard reports a historical dataset. Current human-governed actions appear separately. |
| 0:45–1:35 | Open **Supplier intelligence**, find **Amberwick Office Works**, then open its agreement. | Supplier 1 recorded 24 on-time orders out of 72 due, versus a 95% target under its own terms. That operational gap does not establish legal breach. |
| 1:35–2:25 | Open **Investigations** and ask: “Compare Supplier 1 delivery performance against its contractual SLA and escalation policy.” Open the procurement citation. | The application combines SQL metrics with verified passages. The procedure references the contract’s escalation interval, so the agreement matters. |
| 2:25–3:10 | Choose **Prepare internal review task**. Enter a descriptive title, a review reason, and a future due date. Verify the supporting evidence. Review, save the draft, and submit it. | The exact action is recorded for review. No task has been created yet. |
| 3:10–4:05 | Sign out. Sign in as the reviewer. Open **Approval inbox**, inspect the proposed change and evidence, then explicitly approve. | A separate authorized principal approves the current immutable proposal. The reviewer does not execute it. |
| 4:05–5:00 | Return to the operator. Open **Action proposals**, execute, and inspect the receipt, linked task and audit. Refresh. | PostgreSQL stores the task, receipt and attribution. Retrying the same operation returns the receipt with no duplicate task. |

Use a clear title such as **Review Amberwick delivery performance** in a fresh demo. Add a run label if repeating the walkthrough on the same installation. The release screenshots used a separate synthetic database and genuine authenticated roles.

## Ten-minute engineering walkthrough

Add a historical period change, the SQL denominator, the source version and checksum, and the deterministic Copilot supplier ranking with a follow-up. Open the audit record to show request, action, actor, outcome and links to the proposal. Show that authorization is enforced by the API even when a user sends a direct request. Describe how proposal locks, a unique execution record and the stored operation key handle concurrency. End at **System status**. The supported workspace uses deterministic intelligence and an offline embedding index, while optional Qwen interpretation remains experimental. [Architecture and flow](ARCHITECTURE.md) · [Evidence](STAGE8_REPORT.md)

Only append explicitly attributable demo records to an existing installation. To repeat from a blank workflow history, use the disposable setup and project-specific cleanup in [Quick Start](QUICK_START.md).
