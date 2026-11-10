-- Row-level security per tenant. Repeat for every tenant-owned table.
-- The API sets app.tenant_id per transaction after verifying the JWT and membership:
--   SET LOCAL app.tenant_id = '<tenant uuid>';
-- The app must connect as a role that does NOT own the tables.

ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON bookings
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
