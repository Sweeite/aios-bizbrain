-- Slice 7: Observability — eval labels on spans, approver + before/after on audit_log

-- Add eval label columns to spans (written by ToolExecutor on approve/reject)
ALTER TABLE spans ADD COLUMN IF NOT EXISTS eval_label TEXT;
ALTER TABLE spans ADD COLUMN IF NOT EXISTS eval_note  TEXT;

-- Add approver and before/after state to audit_log
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS approver      TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS before_state  TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS after_state   TEXT;

-- Enforce audit_log immutability via row-level security
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'audit_log' AND policyname = 'audit_log_insert_only'
    ) THEN
        CREATE POLICY audit_log_insert_only
            ON audit_log
            FOR INSERT
            TO authenticated, anon, service_role
            WITH CHECK (true);
    END IF;
END
$$;
