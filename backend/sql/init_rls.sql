-- 1. Enable RLS on all tenant-specific tables
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

-- 2. Create the Isolation Policy
-- This policy says: "A user can only see rows where organization_id matches the session variable 'app.current_org_id'"

CREATE POLICY tenant_isolation_policy ON cases
    USING (organization_id = current_setting('app.current_org_id')::uuid);

CREATE POLICY tenant_isolation_policy ON documents
    USING (organization_id = current_setting('app.current_org_id')::uuid);

CREATE POLICY tenant_isolation_policy ON report_versions
    USING (organization_id = current_setting('app.current_org_id')::uuid);

CREATE POLICY tenant_isolation_policy ON clients
    USING (organization_id = current_setting('app.current_org_id')::uuid);

-- 3. (Important) Allow the 'users' table to be read to find the org_id initially
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_self_access ON users
    USING (id = current_setting('app.current_user_uid', true)); 
    -- Note: We might need a separate logic for bootstrapping login, but this is a good start.
