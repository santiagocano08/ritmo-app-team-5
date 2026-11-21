-- 001_schemas.sql — Create schemas: bronze (landing), silver, gold.
-- Idempotent: IF NOT EXISTS guards let it run on every container start.
-- silver and gold are stubbed empty for forward compatibility (turn 1 scope).
-- Never modified by this script after initial creation.

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
