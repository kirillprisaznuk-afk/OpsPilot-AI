-- Frozen Stage 5 invariants. Invoker privileges only; no SECURITY DEFINER functions.
CREATE FUNCTION workflow_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'immutable workflow record' USING ERRCODE='23514';
END $$;

CREATE FUNCTION workflow_proposal_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE approvals_count integer;
BEGIN
  IF TG_OP='INSERT' THEN
    IF NEW.material->'policy'->>'required_approvals' IS DISTINCT FROM '1'
       OR (NEW.material->'policy'->>'version')::integer IS DISTINCT FROM
          (SELECT policy_id FROM workflow_policy_control WHERE id=1) THEN
      RAISE EXCEPTION 'invalid governance snapshot' USING ERRCODE='23514';
    END IF;
    IF NEW.status<>'DRAFT' THEN
      RAISE EXCEPTION 'new proposals must be draft' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
  END IF;
  IF (to_jsonb(NEW)-ARRAY['status','updated_at']) IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['status','updated_at']) THEN
    RAISE EXCEPTION 'proposal material is immutable; create a revision' USING ERRCODE='23514';
  END IF;
  IF NEW.status=OLD.status THEN RETURN NEW; END IF;
  IF NOT (
    (OLD.status='DRAFT' AND NEW.status IN ('PENDING_REVIEW','CANCELLED','EXPIRED')) OR
    (OLD.status='PENDING_REVIEW' AND NEW.status IN ('APPROVED','REJECTED','CANCELLED','EXPIRED')) OR
    (OLD.status='APPROVED' AND NEW.status IN ('EXECUTING','CANCELLED','EXPIRED')) OR
    (OLD.status='EXECUTING' AND NEW.status IN ('COMPLETED','FAILED'))
  ) THEN RAISE EXCEPTION 'invalid proposal transition' USING ERRCODE='23514'; END IF;
  IF NEW.status IN ('APPROVED','EXECUTING') THEN
    IF NEW.expires_at<=clock_timestamp() THEN
      RAISE EXCEPTION 'expired proposal' USING ERRCODE='23514';
    END IF;
    SELECT count(*) INTO approvals_count FROM workflow_approvals a
      JOIN auth_principals p ON p.id=a.actor_id
      WHERE a.proposal_id=NEW.id AND a.decision='APPROVE' AND a.actor_id<>NEW.proposer_id
      AND a.digest=NEW.digest AND a.proposal_version=NEW.version
      AND a.valid_until>clock_timestamp() AND p.active AND p.is_human
      AND a.authz_version=p.authz_version;
    IF approvals_count < (NEW.material->'policy'->>'required_approvals')::integer THEN
      RAISE EXCEPTION 'valid distinct approval missing' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER workflow_proposal_guard BEFORE INSERT OR UPDATE ON workflow_proposals
  FOR EACH ROW EXECUTE FUNCTION workflow_proposal_guard();

CREATE FUNCTION workflow_approval_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE proposal workflow_proposals; principal record;
BEGIN
  SELECT * INTO proposal FROM workflow_proposals WHERE id=NEW.proposal_id;
  SELECT active,is_human,authz_version INTO principal FROM auth_principals WHERE id=NEW.actor_id;
  IF NEW.actor_id=proposal.proposer_id OR NOT principal.active OR NOT principal.is_human
     OR NEW.authz_version<>principal.authz_version OR NEW.digest<>proposal.digest
     OR NEW.proposal_version<>proposal.version OR proposal.expires_at<=clock_timestamp()
     OR NEW.valid_until>proposal.expires_at OR NEW.valid_until<=clock_timestamp() THEN
    RAISE EXCEPTION 'approval identity, digest or validity mismatch' USING ERRCODE='23514';
  END IF;
  IF EXISTS (
    SELECT 1 FROM jsonb_array_elements_text(proposal.material->'policy'->'scopes') d
    WHERE NOT EXISTS (SELECT 1 FROM auth_role_assignments r
      WHERE r.principal_id=NEW.actor_id AND r.active
      AND r.role_code IN ('WORKFLOW_APPROVER','WORKFLOW_ADMIN')
      AND (r.department_id IS NULL OR r.department_id=d::integer))
  ) THEN RAISE EXCEPTION 'approver scope mismatch' USING ERRCODE='23514'; END IF;
  IF (NEW.decision IN ('APPROVE','REJECT') AND proposal.status<>'PENDING_REVIEW') OR
     (NEW.decision='REVOKE' AND proposal.status<>'APPROVED') THEN
    RAISE EXCEPTION 'proposal is not reviewable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER workflow_approval_guard BEFORE INSERT ON workflow_approvals
  FOR EACH ROW EXECUTE FUNCTION workflow_approval_guard();

CREATE FUNCTION workflow_permission_changed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE auth_principals SET authz_version=authz_version+1 WHERE id=NEW.principal_id;
  RETURN NEW;
END $$;
CREATE TRIGGER workflow_permission_changed AFTER INSERT OR UPDATE ON auth_role_assignments
  FOR EACH ROW EXECUTE FUNCTION workflow_permission_changed();

CREATE FUNCTION workflow_active_effect() RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE material jsonb;
BEGIN
  SELECT p.material INTO material FROM workflow_executions e
    JOIN workflow_proposals p ON p.id=e.proposal_id
    WHERE e.id=nullif(current_setting('opspilot.execution_id',true),'')::uuid
      AND e.status='EXECUTING' AND p.status='EXECUTING'
      AND e.actor_id<>e.approver_id AND p.expires_at>clock_timestamp();
  IF material IS NULL THEN
    RAISE EXCEPTION 'approved active execution required' USING ERRCODE='23514';
  END IF;
  RETURN material;
END $$;

CREATE FUNCTION workflow_task_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE material jsonb; action jsonb; permitted text[];
BEGIN
  material=workflow_active_effect(); action=material->'action';
  IF TG_OP='INSERT' THEN
    IF action->>'type'<>'CREATE_WORKFLOW_TASK' OR
       NEW.execution_id<>current_setting('opspilot.execution_id')::uuid OR
       NOT EXISTS (SELECT 1 FROM workflow_executions WHERE id=NEW.execution_id AND proposal_id=NEW.proposal_id) OR
       NEW.title<>action->>'title' OR NEW.description<>action->>'description' OR
       NEW.department_id<>(material->>'department_id')::integer THEN
      RAISE EXCEPTION 'task creation context mismatch' USING ERRCODE='23514'; END IF;
  ELSE
    IF action->>'task_id' IS DISTINCT FROM OLD.id::text OR
       (action->>'expected_version')::integer IS DISTINCT FROM OLD.version THEN
      RAISE EXCEPTION 'task target mismatch' USING ERRCODE='23514'; END IF;
    permitted=CASE action->>'type'
      WHEN 'ASSIGN_WORKFLOW_TASK' THEN ARRAY['department_id','employee_id']
      WHEN 'UPDATE_WORKFLOW_TASK_STATUS' THEN ARRAY['status','completed_at']
      WHEN 'UPDATE_WORKFLOW_TASK_PRIORITY' THEN ARRAY['priority']
      WHEN 'UPDATE_WORKFLOW_TASK_DUE_DATE' THEN ARRAY['due_at']
      WHEN 'ADD_WORKFLOW_TASK_NOTE' THEN ARRAY[]::text[] END;
    IF permitted IS NULL OR
       (to_jsonb(NEW)-(permitted||ARRAY['version','updated_at'])) IS DISTINCT FROM
       (to_jsonb(OLD)-(permitted||ARRAY['version','updated_at'])) THEN
      RAISE EXCEPTION 'task effect outside approved action' USING ERRCODE='23514'; END IF;
  END IF;
  IF NEW.employee_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM employees WHERE id=NEW.employee_id AND department_id=NEW.department_id
  ) THEN RAISE EXCEPTION 'employee department mismatch' USING ERRCODE='23514'; END IF;
  IF TG_OP='INSERT' THEN
    IF NEW.status<>'open' OR NEW.version<>1 THEN
      RAISE EXCEPTION 'invalid initial task state' USING ERRCODE='23514'; END IF;
    RETURN NEW;
  END IF;
  IF NEW.version<>OLD.version+1 OR
     (to_jsonb(NEW)-ARRAY['status','priority','department_id','employee_id','due_at',
                         'completed_at','version','updated_at']) IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['status','priority','department_id','employee_id','due_at',
                         'completed_at','version','updated_at']) THEN
    RAISE EXCEPTION 'task version or provenance mismatch' USING ERRCODE='23514'; END IF;
  IF NEW.status<>OLD.status AND NOT (
    (OLD.status='open' AND NEW.status IN ('active','cancelled')) OR
    (OLD.status='active' AND NEW.status IN ('blocked','completed','cancelled')) OR
    (OLD.status='blocked' AND NEW.status IN ('active','cancelled'))
  ) THEN RAISE EXCEPTION 'invalid task transition' USING ERRCODE='23514'; END IF;
  IF NEW.due_at IS DISTINCT FROM OLD.due_at AND NEW.due_at<=clock_timestamp() THEN
    RAISE EXCEPTION 'new due date has elapsed' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER workflow_task_guard BEFORE INSERT OR UPDATE ON workflow_tasks
  FOR EACH ROW EXECUTE FUNCTION workflow_task_guard();

CREATE FUNCTION workflow_escalation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE action jsonb;
BEGIN
  action=workflow_active_effect()->'action';
  IF TG_OP='INSERT' THEN
    IF action->>'type'<>'CREATE_INTERNAL_ESCALATION' OR
       NEW.execution_id<>current_setting('opspilot.execution_id')::uuid OR
       NOT EXISTS (SELECT 1 FROM workflow_executions WHERE id=NEW.execution_id AND proposal_id=NEW.proposal_id) THEN
      RAISE EXCEPTION 'escalation creation context mismatch' USING ERRCODE='23514'; END IF;
  ELSIF action->>'type'<>'CLOSE_INTERNAL_ESCALATION' OR
        action->>'escalation_id' IS DISTINCT FROM OLD.id::text OR
        (action->>'expected_version')::integer IS DISTINCT FROM OLD.version THEN
    RAISE EXCEPTION 'escalation target mismatch' USING ERRCODE='23514';
  END IF;
  IF TG_OP='INSERT' THEN
    IF NEW.status<>'open' OR NEW.version<>1 THEN
      RAISE EXCEPTION 'invalid initial escalation state' USING ERRCODE='23514'; END IF;
    IF NEW.task_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM workflow_tasks t WHERE t.id=NEW.task_id AND
        t.subject_id=NEW.subject_id AND t.department_id=NEW.department_id
    ) THEN RAISE EXCEPTION 'related task scope mismatch' USING ERRCODE='23514'; END IF;
    RETURN NEW;
  END IF;
  IF NEW.version<>OLD.version+1 OR OLD.status<>'open' OR NEW.status<>'closed' OR
     (to_jsonb(NEW)-ARRAY['status','closed_at','resolution','version','updated_at']) IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['status','closed_at','resolution','version','updated_at']) THEN
    RAISE EXCEPTION 'escalation version or transition mismatch' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER workflow_escalation_guard BEFORE INSERT OR UPDATE ON workflow_escalations
  FOR EACH ROW EXECUTE FUNCTION workflow_escalation_guard();

CREATE FUNCTION workflow_execution_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status<>'EXECUTING' OR NEW.status NOT IN ('COMPLETED','FAILED') OR
     NEW.proposal_id<>OLD.proposal_id OR NEW.actor_id<>OLD.actor_id OR
     NEW.approver_id<>OLD.approver_id OR NEW.created_at<>OLD.created_at THEN
    RAISE EXCEPTION 'terminal execution is immutable' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER workflow_execution_guard BEFORE UPDATE ON workflow_executions
  FOR EACH ROW EXECUTE FUNCTION workflow_execution_guard();

DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['workflow_audit_events','workflow_approvals','workflow_task_notes',
    'workflow_task_assignments','workflow_evidence','workflow_subjects','workflow_policies',
    'workflow_idempotency_records'] LOOP
    EXECUTE format('CREATE TRIGGER workflow_immutable BEFORE UPDATE OR DELETE ON %I '
                   'FOR EACH ROW EXECUTE FUNCTION workflow_immutable()',t);
  END LOOP;
END $$;

CREATE FUNCTION workflow_child_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE action jsonb;
BEGIN
  action=workflow_active_effect()->'action';
  IF NEW.execution_id<>current_setting('opspilot.execution_id')::uuid OR
     NOT EXISTS (SELECT 1 FROM workflow_executions WHERE id=NEW.execution_id AND actor_id=NEW.actor_id) THEN
    RAISE EXCEPTION 'child execution identity mismatch' USING ERRCODE='23514'; END IF;
  IF TG_TABLE_NAME='workflow_task_notes' THEN
    IF action->>'type'<>'ADD_WORKFLOW_TASK_NOTE' OR action->>'task_id' IS DISTINCT FROM NEW.task_id::text
       OR action->>'text' IS DISTINCT FROM NEW.text THEN
      RAISE EXCEPTION 'note effect mismatch' USING ERRCODE='23514'; END IF;
  ELSIF action->>'type' NOT IN ('CREATE_WORKFLOW_TASK','ASSIGN_WORKFLOW_TASK') THEN
    RAISE EXCEPTION 'assignment effect mismatch' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER workflow_child_guard BEFORE INSERT ON workflow_task_notes
  FOR EACH ROW EXECUTE FUNCTION workflow_child_guard();
CREATE TRIGGER workflow_child_guard BEFORE INSERT ON workflow_task_assignments
  FOR EACH ROW EXECUTE FUNCTION workflow_child_guard();
