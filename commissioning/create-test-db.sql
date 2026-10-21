-- OPERATOR ONLY. Never execute against the existing service cluster on 5432.
-- Run only after specific-host authorization and manual creation of a NEW
-- loopback cluster with bootstrap role meta_commission_bootstrap.
\set ON_ERROR_STOP on
SELECT current_database()='postgres'
   AND current_setting('server_version_num')::integer=180001
   AND current_setting('port')::integer=55480
   AND current_user='meta_commission_bootstrap'
   AND current_setting('data_directory')=:'expected_data_directory'
   AND current_setting('port')::integer=:'expected_port'::integer
   AND current_setting('listen_addresses')='127.0.0.1'
   AND :'test_db' ~ '^meta_commission_[a-z0-9_]+$'
   AND :'test_role' ~ '^meta_commission_[a-z0-9_]+$'
   AND NOT EXISTS(SELECT 1 FROM pg_database WHERE datname NOT IN ('postgres','template0','template1'))
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
