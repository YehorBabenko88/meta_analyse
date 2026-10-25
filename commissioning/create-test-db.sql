-- OPERATOR ONLY. Never execute against the existing service cluster on 5432.
-- Run only after specific-host authorization and manual creation of a NEW
-- loopback cluster with bootstrap role meta_commission_bootstrap.
\set ON_ERROR_STOP on
SET search_path TO pg_catalog;
\if :{?expected_system_identifier}
\else
\echo 'REFUSED: independent file-control identity is required.'
\quit 1
\endif
SELECT pg_catalog.current_database()='postgres'
   AND pg_catalog.current_setting('server_version_num')::pg_catalog.int4=180001
   AND pg_catalog.current_setting('port')::pg_catalog.int4=55480
   AND current_user='meta_commission_bootstrap'
   AND pg_catalog.rtrim(pg_catalog.replace(pg_catalog.current_setting('data_directory'),pg_catalog.chr(92),'/'),'/')=pg_catalog.rtrim(pg_catalog.replace(:'expected_data_directory',pg_catalog.chr(92),'/'),'/')
   AND pg_catalog.current_setting('port')::pg_catalog.int4=:'expected_port'::pg_catalog.int4
   AND pg_catalog.current_setting('listen_addresses')='127.0.0.1'
   AND :'expected_system_identifier' ~ '^[1-9][0-9]{0,19}$'
   AND (pg_catalog.pg_control_system()).system_identifier::pg_catalog.text=:'expected_system_identifier'
   AND :'test_db' ~ '^meta_commission_[a-z0-9_]+$'
   AND :'test_role' ~ '^meta_commission_[a-z0-9_]+$'
   AND pg_catalog.length(:'test_role')<=63
   AND :'test_role'=:'test_db'
   AND :'test_role'<>'meta_commission_bootstrap'
   AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_database WHERE datname NOT IN ('postgres','template0','template1'))
   AS new_private_cluster \gset
\if :new_private_cluster
CREATE ROLE :"test_role" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE :"test_db" OWNER :"test_role" TEMPLATE template0;
-- These revocations are restricted to the newly initialized private cluster.
REVOKE CONNECT ON DATABASE postgres, template1 FROM PUBLIC;
REVOKE ALL ON DATABASE :"test_db" FROM PUBLIC;
GRANT CONNECT,CREATE,TEMPORARY ON DATABASE :"test_db" TO :"test_role";
\echo 'Set the test role password interactively with psql password command; never put it in argv/logs.'
\else
\echo 'REFUSED: fresh private loopback cluster identity not established.'
\quit 1
\endif
