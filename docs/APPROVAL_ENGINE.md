# Approval engine

State machine: DRAFT -> PENDING_REVIEW -> APPROVED -> EXECUTING -> COMPLETED/FAILED. A pending proposal may be rejected. Draft/pending/approved proposals may be cancelled or expire. Revoking a valid approval cancels the approved proposal. FAILED, COMPLETED, REJECTED, CANCELLED and EXPIRED are terminal; failed execution is never blindly retried.

Material is immutable from creation: action and typed arguments, source, proposer, subject, reason, evidence/fact references, policy snapshot, target preconditions, revision and expiry. A revision creates a new UUID and next version with a fresh digest, cancels a live predecessor and inherits no approvals. PATCH is deliberately denied. Database triggers enforce material immutability and legal transitions.

Submit/review/execute requests carry the exact proposal_version and digest that the human inspected. An approver must be a distinct currently active human principal with WORKFLOW_APPROVER or WORKFLOW_ADMIN in every required scope. Even a global administrator cannot approve their own proposal. Identity always comes from a valid bearer session, never a body field, header claiming a role, evidence text or model output.

The initial policy caps proposal validity at 24 hours and approvals at 60 minutes; a normal proposal defaults to two hours. Approval validity cannot exceed proposal/evidence validity. Administrators may version validity settings (proposal 1–168 hours; approval 5–1440 minutes), but cannot disable separation of duties or reduce approval count. The demo policy origin is explicit and distinct from cited corporate documents.

Execution obtains a proposal row lock and principal advisory locks, then rechecks session, permissions, proposer/reviewer authorization versions, current policy, exact digest/version, validity, evidence, source state, target version/lifecycle and employee/scope references. Shared policy locks serialize ordinary mutations with exclusive policy changes. Role revocation invalidates sessions and old approvals. Due dates that have elapsed are rejected.

Proposal views expose effective expiry, stale target/authorization flags, policy currency, approval decisions, execution receipts and evidence limitations. Expiry is checked on access/execution; no background scheduler materializes every expired status. An attempted operation on an expired live proposal records EXPIRED and an audit event.

Human identity here means a trusted locally bootstrapped account classified as human and authenticated by credential possession. This demo does not provide biometric liveness, MFA or proof that a person physically clicked. Tests deliberately issue explicit review requests as a second synthetic human identity; they never treat model text as an approval.
