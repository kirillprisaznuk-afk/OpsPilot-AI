# Using OpsPilot locally

From the repository root in PowerShell, with the accepted Stage 5 local database and accounts:

```powershell
./scripts/start_frontend.ps1 -Build
```

Open `http://127.0.0.1:3106`. On later launches `./scripts/start_frontend.ps1` starts the existing services; `-Open` optionally opens the browser. The launcher checks configuration, existing local accounts, Docker and readiness. It never reseeds or regenerates credentials. If the Stage 5 account setup is missing, use the one-time [Stage 5 setup](AUTHENTICATION_AND_RBAC.md). Keep the generated account file private. The existing database volume and API port 8001 remain intact. No model or API key is required.

Start at **Operations overview**. Pick a historical period, inspect the actual supplier or warehouse measures, and follow the exception links. **Business intelligence** groups procurement, inventory, customer fulfilment, financial exposure, workforce and incident pages. The workflow panel describes current Stage 5 records, not seeded historical tasks.

In **Supplier intelligence**, search a registered supplier, inspect the actual observed SLA gap and open the effective agreement or procedure. In **Knowledge base**, select keyword, vector or hybrid search, open a verified citation and view its registered source. In **Investigations** or **Copilot**, run a real question, inspect the metric scope and references, and follow up in the same signed-in conversation. Verified Intelligence uses zero LLM calls; optional local-model acceptance remains blocked.

To take action, **Prepare a proposal**. Select the actual subject or existing workflow record and enter the relevant parameters. Escalation and investigation-linked drafts require verified evidence. Review exact inputs, save the immutable draft, then submit explicitly. A distinct reviewer opens **Approval inbox**, checks evidence and current state, then confirms approval or rejection. The authorized operator separately requests execution. The resulting receipt links the affected task or escalation and the corresponding audit. If context is stale, prepare a fresh revision; prior approvals do not carry over.

Use **Workflow tasks**, **Internal escalations** and **Audit trail** to inspect persisted work. Current approval states, record versions, assignment history, notes and changes come from the backend. Settings show actual roles and session expiry. Global admins may change supported local role assignments; a change invalidates affected sessions and prior approvals.
