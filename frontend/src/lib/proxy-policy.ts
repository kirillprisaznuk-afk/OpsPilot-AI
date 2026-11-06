const uuid = '[a-f0-9-]{36}',
  number = '[1-9][0-9]*';
const getPaths = [
  '^health$',
  '^ready$',
  '^api/v1/demo/summary$',
  '^api/v1/catalog/(suppliers|warehouses|products)$',
  '^api/v1/operations/(incidents|tasks)$',
  `^api/v1/operations/orders/${number}/timeline$`,
  '^api/v1/analytics/(overview|procurement|suppliers|inventory|warehouses|fulfilment|finance|workforce|incidents|insights)$',
  `^api/v1/analytics/suppliers/${number}$`,
  `^api/v1/analytics/investigations/(supplier|purchase_order|sales_order|shortage|warehouse|incident|invoice|department|task|product)/${number}$`,
  '^api/v1/knowledge/(status|documents)$',
  `^api/v1/knowledge/documents/${number}(/versions/${number})?$`,
  '^api/v1/knowledge/citations/kc_[a-f0-9]{64}$',
  '^api/v1/hybrid/(status|capabilities)$',
  '^api/v1/agent/status$',
  '^api/v1/workflows/(actions|policy|proposals|tasks|escalations|audit|summary)$',
  `^api/v1/workflows/(proposals|tasks|escalations|evidence|executions)/${uuid}$`,
  `^api/v1/workflows/tasks/${uuid}/(notes|assignments)$`,
  '^api/v1/workspace/(subjects|people|principals|actor-labels|status)$',
];
const postPaths = [
  '^api/v1/knowledge/search$',
  '^api/v1/hybrid/query$',
  '^api/v1/workflows/(evidence|recommendations|proposals|policy)$',
  `^api/v1/workflows/proposals/${uuid}/(submit|approve|reject|revoke|cancel|execute|revise)$`,
  `^api/v1/auth/principals/${uuid}/roles$`,
];
export function allowedEndpoint(method: string, path: string) {
  if (path.includes('..') || path.includes('%') || path.includes('\\') || path.length > 300)
    return false;
  return (method === 'GET' ? getPaths : method === 'POST' ? postPaths : []).some((pattern) =>
    new RegExp(pattern).test(path),
  );
}
