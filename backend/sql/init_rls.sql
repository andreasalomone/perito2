-- 1. Enable RLS on all tenant-specific tables
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

-- 2. Enable RLS enforcement for table owners (not just other roles)
-- Without this, table owners can bypass RLS
ALTER TABLE cases FORCE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE report_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE clients FORCE ROW LEVEL SECURITY;

-- 3. Create the Isolation Policy with missing_ok=true
-- This policy says: "A user can only see/modify rows where organization_id matches the session variable 'app.current_org_id'"
-- The second parameter 'true' makes current_setting return NULL instead of error when variable is not set
-- FOR ALL applies to all operations (SELECT, INSERT, UPDATE, DELETE)
-- WITH CHECK ensures new rows also match the policy

CREATE POLICY tenant_isolation_policy ON cases
    FOR ALL
    USING (organization_id = current_setting('app.current_org_id', true)::uuid)
    WITH CHECK (organization_id = current_setting('app.current_org_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON documents
    FOR ALL
    USING (organization_id = current_setting('app.current_org_id', true)::uuid)
    WITH CHECK (organization_id = current_setting('app.current_org_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON report_versions
    FOR ALL
    USING (organization_id = current_setting('app.current_org_id', true)::uuid)
    WITH CHECK (organization_id = current_setting('app.current_org_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON clients
    FOR ALL
    USING (organization_id = current_setting('app.current_org_id', true)::uuid)
    WITH CHECK (organization_id = current_setting('app.current_org_id', true)::uuid);

-- 4. (Important) Allow the 'users' table to be read to find the org_id initially
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_self_access ON users
    USING (id = current_setting('app.current_user_uid', true)); 
    -- Note: We might need a separate logic for bootstrapping login, but this is a good start.
