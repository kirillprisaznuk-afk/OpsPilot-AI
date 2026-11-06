# Stage 5 action registry

All eight actions use strict tagged Pydantic inputs (`extra=forbid`), one distinct human approval and an explicit execution permission. GET /api/v1/workflows/actions returns their input schemas, target, risk and approval requirements. No endpoint directly mutates a task without this pipeline.

| Action | Effect | Key preconditions |
|---|---|---|
| CREATE_WORKFLOW_TASK | Insert an internal task and assignment history | Existing typed subject, valid department/employee, future due date |
| ASSIGN_WORKFLOW_TASK | Change task owner/employee and append assignment | Expected version; permissions in both old/new departments |
| UPDATE_WORKFLOW_TASK_STATUS | Apply allowed lifecycle transition | Expected version; no reopening terminal tasks |
| UPDATE_WORKFLOW_TASK_PRIORITY | Set low/normal/high/urgent | Expected version, nonterminal task |
| UPDATE_WORKFLOW_TASK_DUE_DATE | Set future UTC deadline | Expected version, deadline within 366 days |
| ADD_WORKFLOW_TASK_NOTE | Append inert text and advance version | Expected version; notes allowed after completion |
| CREATE_INTERNAL_ESCALATION | Insert internal escalation | Verified evidence required; related task shares subject/department |
| CLOSE_INTERNAL_ESCALATION | Record internal resolution | Expected version, currently open |

Task transitions: open -> active/cancelled; active -> blocked/completed/cancelled; blocked -> active/cancelled. Completed/cancelled tasks cannot be reopened or reassigned. Escalations move open -> closed once. Every task modification increments its optimistic version, including a note. Task assignment does not edit employee or department source records.

Due dates are timezone-aware, normalized to UTC, checked at drafting and execution, and are proposed operational settings rather than inferred contractual deadlines. Priorities likewise are reviewed settings. The application does not calculate financial penalties or infer legal breach from a performance gap.

Money transfers, invoices/payments, stock changes, supplier/source edits, external emails/messages, contracts, deletion, arbitrary SQL, shell, filesystem and unrestricted tool calls are not registered. Unknown tags and extra fields are rejected before a proposal can be created.
