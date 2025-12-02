--
-- PostgreSQL database dump
--

\restrict dP5uD6bDpGKdUuRKTTz1nEDiCMwQlEvwEWTANpxO1K98mmJJNoqNXQ9Fsar2jTr

-- Dumped from database version 17.7
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


--
-- Name: extractionstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.extractionstatus AS ENUM (
    'SUCCESS',
    'ERROR',
    'SKIPPED',
    'PROCESSING'
);


--
-- Name: reportstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.reportstatus AS ENUM (
    'SUCCESS',
    'ERROR',
    'PROCESSING'
);


--
-- Name: userrole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.userrole AS ENUM (
    'ADMIN',
    'MEMBER'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    user_id character varying(128),
    action character varying(50) NOT NULL,
    resource_type character varying(50),
    resource_id uuid,
    details jsonb,
    ip_address character varying(45),
    created_at timestamp without time zone
);


--
-- Name: cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cases (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    client_id uuid,
    reference_code character varying(100),
    status character varying(50),
    created_at timestamp without time zone
);


--
-- Name: clients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clients (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    vat_number character varying(50),
    created_at timestamp without time zone,
    CONSTRAINT uq_clients_org_name UNIQUE (organization_id, name)
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id uuid NOT NULL,
    case_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    filename character varying(255) NOT NULL,
    gcs_path character varying(1024) NOT NULL,
    mime_type character varying(100),
    ai_status character varying(50),
    ai_extracted_data jsonb,
    created_at timestamp without time zone
);


--
-- Name: ml_training_pairs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ml_training_pairs (
    id uuid NOT NULL,
    case_id uuid,
    ai_version_id uuid,
    final_version_id uuid,
    quality_score double precision,
    created_at timestamp without time zone
);


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: report_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_versions (
    id uuid NOT NULL,
    case_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    version_number integer NOT NULL,
    docx_storage_path character varying(1024),
    is_final boolean,
    ai_raw_output text,
    created_at timestamp without time zone
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id character varying(128) NOT NULL,
    organization_id uuid NOT NULL,
    email character varying(255) NOT NULL,
    role character varying(50)
);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
be5bfcaa2399
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_logs (id, organization_id, user_id, action, resource_type, resource_id, details, ip_address, created_at) FROM stdin;
\.


--
-- Data for Name: cases; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.cases (id, organization_id, client_id, reference_code, status, created_at) FROM stdin;
\.


--
-- Data for Name: clients; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.clients (id, organization_id, name, vat_number, created_at) FROM stdin;
\.


--
-- Data for Name: documents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.documents (id, case_id, organization_id, filename, gcs_path, mime_type, ai_status, ai_extracted_data, created_at) FROM stdin;
\.


--
-- Data for Name: ml_training_pairs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ml_training_pairs (id, case_id, ai_version_id, final_version_id, quality_score, created_at) FROM stdin;
\.


--
-- Data for Name: organizations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.organizations (id, name, created_at) FROM stdin;
63e442d2-fee9-44fe-a2f1-5af9ba4bebf6	My Organization	2025-12-01 15:57:44.126594
\.


--
-- Data for Name: report_versions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.report_versions (id, case_id, organization_id, version_number, docx_storage_path, is_final, ai_raw_output, created_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, organization_id, email, role) FROM stdin;
gxftvo32Wfd0g4Ad93q5R9RrGO42	63e442d2-fee9-44fe-a2f1-5af9ba4bebf6	cuentos.eth@gmail.com	admin
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: cases cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_pkey PRIMARY KEY (id);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: ml_training_pairs ml_training_pairs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ml_training_pairs
    ADD CONSTRAINT ml_training_pairs_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: report_versions report_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_versions
    ADD CONSTRAINT report_versions_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: cases cases_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: cases cases_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: clients clients_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: documents documents_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: documents documents_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: ml_training_pairs ml_training_pairs_ai_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ml_training_pairs
    ADD CONSTRAINT ml_training_pairs_ai_version_id_fkey FOREIGN KEY (ai_version_id) REFERENCES public.report_versions(id);


--
-- Name: ml_training_pairs ml_training_pairs_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ml_training_pairs
    ADD CONSTRAINT ml_training_pairs_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id);


--
-- Name: ml_training_pairs ml_training_pairs_final_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ml_training_pairs
    ADD CONSTRAINT ml_training_pairs_final_version_id_fkey FOREIGN KEY (final_version_id) REFERENCES public.report_versions(id);


--
-- Name: report_versions report_versions_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_versions
    ADD CONSTRAINT report_versions_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: report_versions report_versions_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_versions
    ADD CONSTRAINT report_versions_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: users users_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: cases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cases ENABLE ROW LEVEL SECURITY;

--
-- Name: clients; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;

--
-- Name: documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

--
-- Name: report_versions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.report_versions ENABLE ROW LEVEL SECURITY;

--
-- Name: cases tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.cases USING ((organization_id = (current_setting('app.current_org_id'::text))::uuid));


--
-- Name: clients tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.clients USING ((organization_id = (current_setting('app.current_org_id'::text))::uuid));


--
-- Name: documents tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.documents USING ((organization_id = (current_setting('app.current_org_id'::text))::uuid));


--
-- Name: report_versions tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.report_versions USING ((organization_id = (current_setting('app.current_org_id'::text))::uuid));


--
-- Name: users user_self_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY user_self_access ON public.users USING (((id)::text = current_setting('app.current_user_uid'::text, true)));


--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: idx_cases_dashboard; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cases_dashboard ON public.cases USING btree (organization_id, created_at DESC);


--
-- Name: idx_documents_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_case ON public.documents USING btree (case_id);


--
-- Name: idx_ml_pairs_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ml_pairs_case ON public.ml_training_pairs USING btree (case_id);


--
-- Name: idx_report_versions_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_report_versions_case ON public.report_versions USING btree (case_id);


--
-- Name: idx_users_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_org ON public.users USING btree (organization_id);

--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: -
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

\unrestrict dP5uD6bDpGKdUuRKTTz1nEDiCMwQlEvwEWTANpxO1K98mmJJNoqNXQ9Fsar2jTr

