# Business capability registry

The canonical registry is `backend/app/hybrid/registry.py`; the live API exposes
`GET /api/v1/hybrid/capabilities`. These are existing business-service capabilities,
not a question-to-answer table. Every capability declares its domain, objectives,
entity types, tool bindings, required evidence, metrics, parameters, output types,
semantics, unsupported assumptions, permission and bounded resource estimate.

All require validated observation scope. Supplier detail/SLA/contracts require a
resolved supplier or a verified runtime rank binding. Other filters are optional
only where supported by the existing service. Unsupported combinations clarify
rather than silently inventing a narrower calculation.

| Capability | Domain | Subject types | Existing tools | Required evidence |
|---|---|---|---|---|
| supplier_performance | procurement | supplier | get_supplier_performance | metrics |
| supplier_ranking | procurement | scoped aggregate / resolved investigation root | compare_suppliers | ranked_population |
| supplier_sla | procurement | supplier | get_supplier_performance, search_corporate_knowledge | metrics, supplier_agreement |
| contract_lookup | procurement | supplier | get_supplier_performance, search_corporate_knowledge | supplier_agreement |
| policy_lookup | knowledge | scoped aggregate / resolved investigation root | search_corporate_knowledge | policy |
| inventory | inventory | scoped aggregate / resolved investigation root | get_inventory_status | metrics |
| warehouse | warehousing | scoped aggregate / resolved investigation root | get_warehouse_performance | metrics |
| fulfilment | sales | scoped aggregate / resolved investigation root | get_customer_fulfilment | metrics |
| recorded_costs | finance | scoped aggregate / resolved investigation root | get_operational_costs | metrics |
| workforce | workforce | scoped aggregate / resolved investigation root | get_workforce_tasks | metrics |
| incidents | operations | scoped aggregate / resolved investigation root | get_operational_incidents | metrics |
| procurement | procurement | scoped aggregate / resolved investigation root | get_procurement_performance | metrics |
| investigation | cross_domain | scoped aggregate / resolved investigation root | investigate_business_entity | relationships |
| overview | enterprise | scoped aggregate / resolved investigation root | get_enterprise_overview | metrics |

Ranking supports on-time rate, overdue outstanding order count, overdue commitment,
open commitment and SLA gap. Sorts use the existing complete supplier snapshot,
exact numeric values, nulls last and stable supplier IDs. The planner does not
calculate or round independent business metrics.

The compact ontology distinguishes supplier/contract/purchase order/receipt/stock
movement, warehouse/product, customer/sales order/fulfilment promise, invoice/cost,
employee/department/task/incident and policy/evidence. Typed relationship records
from Stage 2 carry actual identity, timestamps, source references and evidence class.
The code-level relationship catalogue describes supported semantic boundaries:

- supplier → purchase_order: supplies.
- purchase_order → receipt: received_against.
- receipt → stock_movement: records_inventory.
- stock_movement → product: concerns.
- sales_order → customer: ordered_by.
- fulfilment → sales_order: dispatches_against.
- supplier_contract → supplier: defines_supplier_obligations.
- policy → procedure: governs.
- incident → task: linked_corrective_work.
- recorded_cost → invoice: recorded_financial_basis.

Permission is always `read_business_and_synthetic_knowledge`; writes, unrecorded
losses and automatic penalties are unsupported. The language model cannot create a
capability, tool, filter field, entity ID or permission. Extension requires adding a
registered binding, typed intent/argument validation, evidence requirements and
independent numerical/source/negative tests. No schema or business dataset change
is required for the current registry.
