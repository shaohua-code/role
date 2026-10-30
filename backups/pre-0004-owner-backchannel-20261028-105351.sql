--
-- PostgreSQL database dump
--

\restrict gw2pJ0WNxCnBAY8P8IBlQmDR6uv0DLyTRKWqYsuF0qlGetdYI2Vqd7XT8ejwseE

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO iam;

--
-- Name: application_resources; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.application_resources (
    id uuid NOT NULL,
    application_id uuid NOT NULL,
    parent_id uuid,
    resource_type character varying(20) NOT NULL,
    code character varying(180) NOT NULL,
    name character varying(160) NOT NULL,
    path character varying(300),
    icon character varying(120),
    sort integer DEFAULT 0 NOT NULL,
    extra json DEFAULT '{}'::json NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    description character varying(500),
    CONSTRAINT ck_application_resource_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'disabled'::character varying])::text[]))),
    CONSTRAINT ck_application_resource_type CHECK (((resource_type)::text = ANY ((ARRAY['menu'::character varying, 'button'::character varying, 'data_rule'::character varying])::text[])))
);


ALTER TABLE public.application_resources OWNER TO iam;

--
-- Name: application_themes; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.application_themes (
    id uuid NOT NULL,
    application_id uuid NOT NULL,
    version integer NOT NULL,
    status character varying(20) NOT NULL,
    config json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    published_at timestamp with time zone
);


ALTER TABLE public.application_themes OWNER TO iam;

--
-- Name: applications; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.applications (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    client_id character varying(160) NOT NULL,
    permission_namespace character varying(100) NOT NULL,
    client_secret_hash character varying(255),
    name character varying(160) NOT NULL,
    description character varying(500),
    redirect_uris json NOT NULL,
    post_logout_redirect_uris json NOT NULL,
    trusted boolean NOT NULL,
    registration_policy character varying(20) DEFAULT 'disabled'::character varying NOT NULL,
    registration_role_id uuid,
    registration_terms_version character varying(80),
    registration_privacy_version character varying(80),
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_application_registration_policy CHECK (((registration_policy)::text = ANY ((ARRAY['disabled'::character varying, 'open'::character varying])::text[])))
);


ALTER TABLE public.applications OWNER TO iam;

--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.audit_events (
    id uuid NOT NULL,
    actor_user_id uuid,
    tenant_id uuid,
    action character varying(120) NOT NULL,
    target_type character varying(80) NOT NULL,
    target_id character varying(180),
    outcome character varying(20) NOT NULL,
    source_ip character varying(64),
    details json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.audit_events OWNER TO iam;

--
-- Name: login_attempt_buckets; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.login_attempt_buckets (
    key_hash character varying(64) NOT NULL,
    failed_attempts integer DEFAULT 0 NOT NULL,
    window_started_at timestamp with time zone NOT NULL,
    blocked_until timestamp with time zone,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_login_attempt_buckets_nonnegative CHECK ((failed_attempts >= 0))
);


ALTER TABLE public.login_attempt_buckets OWNER TO iam;

--
-- Name: membership_organizations; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.membership_organizations (
    membership_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    is_primary boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.membership_organizations OWNER TO iam;

--
-- Name: model_catalog; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.model_catalog (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    key character varying(100) NOT NULL,
    provider character varying(100) NOT NULL,
    model_name character varying(160) NOT NULL,
    display_name character varying(160) NOT NULL,
    endpoint_url character varying(500),
    credential_ref character varying(300),
    capabilities json NOT NULL,
    rpm_limit integer,
    tpm_limit integer,
    input_cost_per_million numeric(12,6),
    output_cost_per_million numeric(12,6),
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.model_catalog OWNER TO iam;

--
-- Name: model_usage_events; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.model_usage_events (
    id uuid NOT NULL,
    request_id character varying(180) NOT NULL,
    tenant_id uuid NOT NULL,
    model_id uuid NOT NULL,
    application_id uuid NOT NULL,
    user_id uuid NOT NULL,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    estimated_cost numeric(18,8),
    outcome character varying(20) NOT NULL,
    usage_is_estimated boolean DEFAULT false NOT NULL,
    source character varying(32) DEFAULT 'gateway'::character varying NOT NULL,
    latency_ms integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_model_usage_nonnegative CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND ((latency_ms IS NULL) OR (latency_ms >= 0)))),
    CONSTRAINT ck_model_usage_outcome CHECK (((outcome)::text = ANY ((ARRAY['succeeded'::character varying, 'failed'::character varying])::text[]))),
    CONSTRAINT ck_model_usage_source CHECK (((source)::text = ANY ((ARRAY['gateway'::character varying, 'admin_reconciliation'::character varying])::text[])))
);


ALTER TABLE public.model_usage_events OWNER TO iam;

--
-- Name: model_usage_reservations; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.model_usage_reservations (
    id uuid NOT NULL,
    request_id character varying(180) NOT NULL,
    tenant_id uuid NOT NULL,
    model_id uuid NOT NULL,
    application_id uuid NOT NULL,
    user_id uuid NOT NULL,
    reserved_input_tokens integer NOT NULL,
    reserved_output_tokens integer NOT NULL,
    status character varying(20) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    settled_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_model_usage_reservation_status CHECK (((status)::text = ANY ((ARRAY['reserved'::character varying, 'settled'::character varying, 'released'::character varying])::text[]))),
    CONSTRAINT ck_model_usage_reservation_tokens_nonnegative CHECK (((reserved_input_tokens >= 0) AND (reserved_output_tokens >= 0)))
);


ALTER TABLE public.model_usage_reservations OWNER TO iam;

--
-- Name: oauth_authorization_codes; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.oauth_authorization_codes (
    id uuid NOT NULL,
    application_id uuid NOT NULL,
    user_id uuid NOT NULL,
    auth_version integer NOT NULL,
    membership_version integer DEFAULT 1 NOT NULL,
    code_hash character varying(64) NOT NULL,
    redirect_uri text NOT NULL,
    scope character varying(500) NOT NULL,
    nonce character varying(255) NOT NULL,
    code_challenge character varying(128) NOT NULL,
    code_challenge_method character varying(10) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.oauth_authorization_codes OWNER TO iam;

--
-- Name: oauth_consent_requests; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.oauth_consent_requests (
    id uuid NOT NULL,
    application_id uuid NOT NULL,
    user_id uuid NOT NULL,
    auth_version integer NOT NULL,
    membership_version integer DEFAULT 1 NOT NULL,
    ticket_hash character varying(64) NOT NULL,
    redirect_uri text NOT NULL,
    client_state character varying(512) NOT NULL,
    scope character varying(500) NOT NULL,
    nonce character varying(255) NOT NULL,
    code_challenge character varying(128) NOT NULL,
    code_challenge_method character varying(10) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.oauth_consent_requests OWNER TO iam;

--
-- Name: oauth_refresh_tokens; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.oauth_refresh_tokens (
    id uuid NOT NULL,
    family_id uuid NOT NULL,
    application_id uuid NOT NULL,
    user_id uuid NOT NULL,
    auth_version integer NOT NULL,
    membership_version integer DEFAULT 1 NOT NULL,
    token_hash character varying(64) NOT NULL,
    scope character varying(500) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    replaced_by_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.oauth_refresh_tokens OWNER TO iam;

--
-- Name: organizations; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.organizations (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    parent_id uuid,
    key character varying(100) NOT NULL,
    name character varying(160) NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.organizations OWNER TO iam;

--
-- Name: password_reset_throttles; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.password_reset_throttles (
    email_hash character varying(64) NOT NULL,
    last_requested_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL
);


ALTER TABLE public.password_reset_throttles OWNER TO iam;

--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.password_reset_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.password_reset_tokens OWNER TO iam;

--
-- Name: permissions; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.permissions (
    id uuid NOT NULL,
    code character varying(180) NOT NULL,
    catalog_namespace character varying(100) NOT NULL,
    resource_type character varying(100) NOT NULL,
    scope character varying(80) NOT NULL,
    description character varying(500),
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    surface character varying(20) DEFAULT 'business'::character varying NOT NULL,
    requires_data_scope boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_permission_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'disabled'::character varying])::text[]))),
    CONSTRAINT ck_permission_surface CHECK (((surface)::text = ANY ((ARRAY['management'::character varying, 'business'::character varying])::text[])))
);


ALTER TABLE public.permissions OWNER TO iam;

--
-- Name: public_registration_challenges; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.public_registration_challenges (
    id uuid NOT NULL,
    application_id uuid NOT NULL,
    email_hash character varying(64) NOT NULL,
    email character varying(320) NOT NULL,
    display_name character varying(120) NOT NULL,
    existing_user_id uuid,
    verification_code_hash character varying(64) NOT NULL,
    registration_role_id uuid,
    registration_role_fingerprint character varying(64),
    terms_version character varying(80) NOT NULL,
    privacy_version character varying(80) NOT NULL,
    terms_url character varying(2048) NOT NULL,
    privacy_url character varying(2048) NOT NULL,
    failed_attempts integer DEFAULT 0 NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_registration_challenge_role_snapshot_required CHECK (((consumed_at IS NOT NULL) OR ((registration_role_id IS NOT NULL) AND (registration_role_fingerprint IS NOT NULL)))),
    CONSTRAINT ck_registration_failed_attempts_nonnegative CHECK ((failed_attempts >= 0))
);


ALTER TABLE public.public_registration_challenges OWNER TO iam;

--
-- Name: public_registration_consents; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.public_registration_consents (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    application_id uuid NOT NULL,
    terms_version character varying(80) NOT NULL,
    privacy_version character varying(80) NOT NULL,
    terms_url character varying(2048) NOT NULL,
    privacy_url character varying(2048) NOT NULL,
    source_ip character varying(64),
    accepted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.public_registration_consents OWNER TO iam;

--
-- Name: public_registration_email_outbox; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.public_registration_email_outbox (
    id uuid NOT NULL,
    challenge_id uuid NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    retry_after timestamp with time zone DEFAULT now() NOT NULL,
    locked_until timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_registration_outbox_attempts_nonnegative CHECK ((attempts >= 0)),
    CONSTRAINT ck_registration_outbox_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'sending'::character varying, 'sent'::character varying, 'failed'::character varying])::text[])))
);


ALTER TABLE public.public_registration_email_outbox OWNER TO iam;

--
-- Name: public_registration_throttles; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.public_registration_throttles (
    bucket_hash character varying(64) NOT NULL,
    last_requested_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL
);


ALTER TABLE public.public_registration_throttles OWNER TO iam;

--
-- Name: refresh_sessions; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.refresh_sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(64) NOT NULL,
    auth_version integer NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.refresh_sessions OWNER TO iam;

--
-- Name: revoked_access_tokens; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.revoked_access_tokens (
    jti_hash character varying(64) NOT NULL,
    token_use character varying(24) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.revoked_access_tokens OWNER TO iam;

--
-- Name: role_application_resources; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.role_application_resources (
    role_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.role_application_resources OWNER TO iam;

--
-- Name: role_bindings; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.role_bindings (
    id uuid NOT NULL,
    membership_id uuid NOT NULL,
    role_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.role_bindings OWNER TO iam;

--
-- Name: role_data_scopes; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.role_data_scopes (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL,
    scope_type character varying(32) NOT NULL,
    organization_ids json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_data_scope_type CHECK (((scope_type)::text = ANY ((ARRAY['tenant'::character varying, 'self'::character varying, 'organization'::character varying, 'organization_tree'::character varying, 'selected_organizations'::character varying])::text[])))
);


ALTER TABLE public.role_data_scopes OWNER TO iam;

--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.role_permissions (
    id uuid NOT NULL,
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL,
    resource_id character varying(180)
);


ALTER TABLE public.role_permissions OWNER TO iam;

--
-- Name: roles; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.roles (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    application_id uuid,
    kind character varying(20) NOT NULL,
    key character varying(100) NOT NULL,
    name character varying(120) NOT NULL,
    description character varying(500),
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_role_kind CHECK (((kind)::text = ANY ((ARRAY['platform'::character varying, 'tenant'::character varying, 'application'::character varying])::text[])))
);


ALTER TABLE public.roles OWNER TO iam;

--
-- Name: tenant_memberships; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.tenant_memberships (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    status character varying(20) NOT NULL,
    auth_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_tenant_membership_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'disabled'::character varying, 'departed'::character varying])::text[])))
);


ALTER TABLE public.tenant_memberships OWNER TO iam;

--
-- Name: tenants; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.tenants (
    id uuid NOT NULL,
    name character varying(120) NOT NULL,
    slug character varying(80) NOT NULL,
    kind character varying(20) DEFAULT 'organization'::character varying NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_tenant_kind CHECK (((kind)::text = ANY ((ARRAY['organization'::character varying, 'consumer'::character varying])::text[])))
);


ALTER TABLE public.tenants OWNER TO iam;

--
-- Name: user_group_memberships; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.user_group_memberships (
    group_id uuid NOT NULL,
    membership_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_group_memberships OWNER TO iam;

--
-- Name: user_group_roles; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.user_group_roles (
    group_id uuid NOT NULL,
    role_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_group_roles OWNER TO iam;

--
-- Name: user_groups; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.user_groups (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    key character varying(100) NOT NULL,
    name character varying(120) NOT NULL,
    description character varying(500),
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_groups OWNER TO iam;

--
-- Name: user_invitations; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.user_invitations (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    role_id uuid NOT NULL,
    email character varying(320) NOT NULL,
    display_name character varying(120) NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    accepted_at timestamp with time zone,
    revoked_at timestamp with time zone,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_invitations OWNER TO iam;

--
-- Name: users; Type: TABLE; Schema: public; Owner: iam
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(320),
    phone_number character varying(32),
    password_hash character varying(255) NOT NULL,
    display_name character varying(120) NOT NULL,
    status character varying(20) NOT NULL,
    auth_version integer NOT NULL,
    email_verified_at timestamp with time zone,
    phone_verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_user_has_login_id CHECK (((email IS NOT NULL) OR (phone_number IS NOT NULL))),
    CONSTRAINT ck_user_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'disabled'::character varying, 'locked'::character varying])::text[])))
);


ALTER TABLE public.users OWNER TO iam;

--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.alembic_version (version_num) FROM stdin;
0003_resource_description
\.


--
-- Data for Name: application_resources; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.application_resources (id, application_id, parent_id, resource_type, code, name, path, icon, sort, extra, status, created_at, description) FROM stdin;
275a4c2e-7001-4573-a265-7d89c918111a	5fd4169f-b222-4864-b00a-95325083ce25	\N	menu	deel	菜单	/lo	11	0	{}	active	2026-10-27 09:24:43.633214+00	\N
25cf0585-8fcf-4734-9253-6cd6e5bb4d89	5fd4169f-b222-4864-b00a-95325083ce25	275a4c2e-7001-4573-a265-7d89c918111a	menu	123	123	123123	\N	0	{}	active	2026-10-27 09:25:07.545137+00	\N
88209f5c-033b-43f7-82a4-a6d92f89577c	5fd4169f-b222-4864-b00a-95325083ce25	25cf0585-8fcf-4734-9253-6cd6e5bb4d89	button	12311	32111	\N	\N	0	{}	active	2026-10-27 09:25:52.904027+00	\N
\.


--
-- Data for Name: application_themes; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.application_themes (id, application_id, version, status, config, created_at, published_at) FROM stdin;
\.


--
-- Data for Name: applications; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.applications (id, tenant_id, client_id, permission_namespace, client_secret_hash, name, description, redirect_uris, post_logout_redirect_uris, trusted, registration_policy, registration_role_id, registration_terms_version, registration_privacy_version, status, created_at) FROM stdin;
a680e9d6-654f-492a-85b1-ef428bd97976	fe4a8854-cc40-451d-842a-930a3c816356	demo-app	demo	\N	演示应用	绿场四级走查演示应用	["http://localhost:3000/callback"]	["http://localhost:3000/"]	f	disabled	\N	\N	\N	active	2026-10-23 16:53:14.473478+00
27bf3137-7910-4544-9e62-9789d97aab0c	9c87c06c-6adf-4335-b06b-362512ec62c2	crud-demo	crud	$argon2id$v=19$m=65536,t=3,p=4$XlyeLzSILokLAmHBSQresw$uozAWaU6OZsCH7HAh3tiSSLZBb23nmbpijg7pc/EKTU	CRUD Demo	SDK 五件套联调示例应用	["http://localhost:8000/auth/callback"]	[]	f	disabled	\N	\N	\N	active	2026-10-24 07:20:26.896679+00
5fd4169f-b222-4864-b00a-95325083ce25	9c87c06c-6adf-4335-b06b-362512ec62c2	deerflow	deerflow	$argon2id$v=19$m=65536,t=3,p=4$Q2fEtjB1g50U8kLnpfY4iA$E6DK2Ku4GXmuxqoeSX5iAabpMyqXm7qv0ha6b7vVJFg	DeerFlow	DeerFlow greenfield SDK 2.x	["http://localhost:8001/api/v1/auth/callback/central-iam"]	[]	t	disabled	\N	\N	\N	active	2026-10-24 07:37:33.258979+00
\.


--
-- Data for Name: audit_events; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.audit_events (id, actor_user_id, tenant_id, action, target_type, target_id, outcome, source_ip, details, created_at) FROM stdin;
12295ab5-6784-4ccc-8b66-605fac68ed25	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-23 16:29:58.873307+00
d5bc847f-0e59-44b2-be14-715517550282	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-23 16:51:53.301172+00
753d033c-befd-421f-9226-75827adc3c4e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-23 16:53:59.19682+00
8decd384-4e21-4190-9ed5-01eb7eb540bb	3d84740b-fcc5-401a-89cc-8408ccd004da	\N	auth.login	user	3d84740b-fcc5-401a-89cc-8408ccd004da	success	172.18.0.1	{}	2026-10-23 16:53:59.489652+00
d15221ab-8327-4279-bd80-5d488364ff6f	08b2ecea-9232-4479-9c47-dbcd2befc0af	\N	auth.login	user	08b2ecea-9232-4479-9c47-dbcd2befc0af	success	172.18.0.1	{}	2026-10-23 16:53:59.65762+00
5f0344a4-3afe-4133-8de8-29d096e0b8a3	427efcf4-76a2-4200-8911-807d53aec55b	\N	auth.login	user	427efcf4-76a2-4200-8911-807d53aec55b	success	172.18.0.1	{}	2026-10-23 16:53:59.8086+00
f91441a6-d41c-4c3c-bcb8-c32ccc8a4517	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-23 16:53:59.974738+00
98ea92bb-9af4-47ae-b5c7-30582f4bedf7	427efcf4-76a2-4200-8911-807d53aec55b	\N	auth.login	user	427efcf4-76a2-4200-8911-807d53aec55b	success	172.18.0.1	{}	2026-10-23 16:54:14.717839+00
84c7806d-7e69-4f55-86a7-80b58dcc0137	427efcf4-76a2-4200-8911-807d53aec55b	\N	auth.login	user	427efcf4-76a2-4200-8911-807d53aec55b	success	172.18.0.1	{}	2026-10-23 16:54:14.972644+00
c7db5e17-e24b-4a7a-b1fb-a0fd4febfbc8	427efcf4-76a2-4200-8911-807d53aec55b	\N	auth.login	user	427efcf4-76a2-4200-8911-807d53aec55b	success	172.18.0.1	{}	2026-10-23 16:58:00.685594+00
35c66a1e-5912-4a6f-b916-de2bd5743947	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-23 22:59:55.894006+00
7cba5a69-b640-4c10-a249-13f241f31bd6	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 05:01:25.99824+00
cd13d576-1b44-4320-b369-6bf62c7aca62	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 06:56:31.655965+00
3dcdadd0-5cf4-46f5-9294-9de77e4b5185	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	denied	172.18.0.1	{}	2026-10-24 07:03:05.884608+00
eedb5547-f32d-4733-a93d-5da89084d61b	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	denied	172.18.0.1	{}	2026-10-24 07:03:06.125932+00
481503cd-9c4b-40d6-960e-a68335509bd8	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	denied	172.18.0.1	{}	2026-10-24 07:03:06.295908+00
b47e2017-deba-4bdf-8e24-ccec0ee1904b	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	denied	172.18.0.1	{}	2026-10-24 07:03:06.453945+00
4f21f9cd-59d8-4414-93be-ce48a02e56f1	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	denied	172.18.0.1	{}	2026-10-24 07:03:06.608123+00
5320edec-aa79-4490-842e-eec2f77deb46	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	denied	172.18.0.1	{}	2026-10-24 07:03:06.771592+00
422fa8aa-4c47-4735-9f4b-04b5ccaae3fd	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:03:28.409008+00
4896c492-8d52-4ab1-8957-666f46bb0117	427efcf4-76a2-4200-8911-807d53aec55b	\N	auth.login	user	427efcf4-76a2-4200-8911-807d53aec55b	success	172.18.0.1	{}	2026-10-24 07:03:28.703885+00
e498c593-7828-4298-91c0-d1f6a0340241	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:20:26.620814+00
4a7d7bd1-b24f-4fe9-9e14-cee0b82e7edd	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application.create	application	27bf3137-7910-4544-9e62-9789d97aab0c	success	172.18.0.1	{"client_id": "crud-demo", "tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "trusted": false}	2026-10-24 07:20:26.896679+00
4d27adf7-d4cc-421b-9fe4-0fb0c851a6b6	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:20:47.25876+00
529c8dbe-1a10-4ee5-ba1b-6374bfe9e39b	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:21:04.271127+00
08b23d1d-e34a-4410-ba1d-2fb511450055	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:21:33.947504+00
f2707646-6eee-42cc-a8c7-e2b1fc097dcb	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	e9269041-5acd-45d2-80bc-f809ca90c516	success	172.18.0.1	{"code": "crud.document.read", "catalog_namespace": "crud", "application_id": "27bf3137-7910-4544-9e62-9789d97aab0c"}	2026-10-24 07:21:34.184765+00
30d3cb1f-25a3-4030-bfa0-8f225fc8363a	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:21:50.774337+00
2058d941-cc32-49e9-abcb-e717f3820601	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	52eacaae-aa6d-4fdf-a33d-7b94976ca821	success	172.18.0.1	{"code": "crud.document.create", "catalog_namespace": "crud", "application_id": "27bf3137-7910-4544-9e62-9789d97aab0c"}	2026-10-24 07:21:51.026843+00
b6aa11ea-ac0d-41ea-a319-12166d7b5534	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	9d9fa83e-c39e-4f58-8302-5ebc343b82c7	success	172.18.0.1	{"code": "crud.document.delete", "catalog_namespace": "crud", "application_id": "27bf3137-7910-4544-9e62-9789d97aab0c"}	2026-10-24 07:21:51.070387+00
ef71e83c-63ff-4c8b-81f1-fda06fe25989	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.create	role	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2"}	2026-10-24 07:21:51.184075+00
d884989a-ca8b-4df6-8064-964652fc9b17	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	success	172.18.0.1	{"permission": "crud.document.read", "resource_id": null}	2026-10-24 07:21:51.309608+00
0cc81475-d8a7-42fd-874d-2d2f25f5a249	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	success	172.18.0.1	{"permission": "crud.document.create", "resource_id": null}	2026-10-24 07:21:51.374301+00
f0aac0ad-fd38-44c1-9e61-14f40ebfedb9	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	success	172.18.0.1	{"permission": "crud.document.delete", "resource_id": null}	2026-10-24 07:21:51.417532+00
922653b1-2515-459d-afa2-a8588b74d489	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.data_scopes.replace	role	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "policy_count": 3}	2026-10-24 07:21:51.482006+00
d4b061c9-ca20-429e-9f38-3acdae5c4103	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	user.create	user	0691da35-9905-4b03-a3d1-f07578e09ac8	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_id": "c287b677-9d9e-4c4a-8cb0-cd82d2d27671"}	2026-10-24 07:21:51.645196+00
999f6bc9-681a-4059-93db-9261107315e1	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:35:14.293146+00
a58c7bea-533f-4cfa-a286-1217d96e0839	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:35:32.108888+00
6eae44b6-f0a1-4a5d-9d22-fbbafbf710e8	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:37:33.016185+00
f8bdefb7-a503-49ab-b747-a384f38335ed	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "trusted": false}	2026-10-24 07:37:33.258979+00
fd5b41a9-b94b-45c9-bbaf-8e5e1f96be18	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	1955ea73-e035-431d-a86a-be9e5c4600ea	success	172.18.0.1	{"code": "deerflow.preference.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.512683+00
59d1bb89-a8a1-4208-9535-2cc686300111	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	099af76d-fe81-4736-b200-898b53e65b88	success	172.18.0.1	{"code": "deerflow.preference.write", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.553304+00
20684140-d417-4676-9f00-5b003efe9ec3	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.create	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2"}	2026-10-24 07:37:35.002998+00
085bca78-e4a3-4757-9a43-ef59a226a29d	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	e94346df-56ae-494d-8ce8-af9be7d3f5a8	success	172.18.0.1	{"code": "deerflow.project.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.604251+00
8ca86522-6ecb-4199-94d4-74f797075838	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	d6271b0f-729d-49f3-b4f1-9146ea684850	success	172.18.0.1	{"code": "deerflow.project.delete", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.697283+00
f93e9d33-553c-473b-8954-e7f9d1161970	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	b58b3152-f96c-427c-8754-acb9d85bff69	success	172.18.0.1	{"code": "deerflow.thread.write", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.771997+00
0f8c8e12-0cf3-475f-befd-342fecd1fb61	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	5ea79933-3369-4020-991f-a50809571caa	success	172.18.0.1	{"code": "deerflow.run.create", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.841804+00
2b47d815-0f66-4277-84a5-79169f8ca4fc	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	d2bcf175-8d20-450b-a5cf-2bb73053ad11	success	172.18.0.1	{"code": "deerflow.run.cancel", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.931655+00
53b97403-8689-4815-ae6d-1b0258359e9e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	6e653603-2458-4ee7-8ace-566c56dc1719	success	172.18.0.1	{"code": "deerflow.agent.write", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.054913+00
f020ff40-2367-4c5e-aba8-df8f976c56e9	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	1f025374-040d-4f76-84d3-6bf2066dbe68	success	172.18.0.1	{"code": "deerflow.agent.admin", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.142183+00
7ef0ec5d-9b21-441f-825c-d9efed458a85	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	afb8e08f-ba6d-4605-8d15-86d6415d4997	success	172.18.0.1	{"code": "deerflow.memory.write", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.241235+00
f214b8f4-b1a9-42cb-a1d6-394cf85885e1	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	74278a34-2fac-466c-b928-28b18e797f9b	success	172.18.0.1	{"code": "deerflow.memory.admin", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.308304+00
56c5a8df-349c-4764-b79e-8432d12b74b2	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	1dc4588e-36ee-4040-af55-b31fb5c82cef	success	172.18.0.1	{"code": "deerflow.channel.write", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.372847+00
5091bea4-c2af-40ad-a0ca-6c4541f2fd5f	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	c333f013-4acd-47a6-a8e5-e3ca459096c5	success	172.18.0.1	{"code": "deerflow.integration.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.458426+00
348be8df-ba13-427e-9e04-32f56529d2f6	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	8a908a46-32e9-43a4-a5b0-8cdd169a5fbf	success	172.18.0.1	{"code": "deerflow.integration.admin", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.520139+00
618da582-6757-4af9-bfcb-4420eb215cf0	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	1eeb66f2-3ed8-46be-a555-43d8590c1d16	success	172.18.0.1	{"code": "deerflow.skill.write", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.597047+00
886fa7ce-c21e-4b6a-a6c4-c05f2e1bcd75	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	f72afa56-d671-472d-bb1d-d78848075e84	success	172.18.0.1	{"code": "deerflow.skill.admin", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.657982+00
9cbcac96-ac5f-4591-bc15-cb7c0deacdcc	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	dfbd60b6-4b24-4d03-a09b-ce210b354c7e	success	172.18.0.1	{"code": "deerflow.subagent.admin", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.718265+00
c546d955-0430-470c-ad03-29130392aed7	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	98d380a0-0ad0-4cb7-b335-e09911444bca	success	172.18.0.1	{"code": "deerflow.model.list", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.815409+00
8edec01c-0c11-4f91-884c-9f1754a18656	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	6c69bfb4-6849-404f-9087-e7edd64bfcd1	success	172.18.0.1	{"code": "deerflow.tool.use", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.892675+00
46a13ea5-6fe4-43d6-a683-b938bd4ddeb2	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.preference.read", "resource_id": null}	2026-10-24 07:37:35.095913+00
70b249d9-a2e2-44a3-800e-6a935d89ade9	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.project.delete", "resource_id": null}	2026-10-24 07:37:35.27669+00
8f3e3b9d-95b6-4466-a29a-156955b32ecc	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.run.create", "resource_id": null}	2026-10-24 07:37:35.430993+00
30e27ea4-b71a-4fc6-8129-d167f3a68ae2	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.agent.write", "resource_id": null}	2026-10-24 07:37:35.591762+00
c6865141-3bde-4632-b8fd-beb8a7a6ad4a	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.memory.write", "resource_id": null}	2026-10-24 07:37:35.7765+00
93ba5970-8f80-4d22-bb1c-b6cb40bc6291	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.channel.write", "resource_id": null}	2026-10-24 07:37:35.978435+00
63bdf999-599a-452a-a5ad-e06f8d9415e4	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.integration.admin", "resource_id": null}	2026-10-24 07:37:36.17407+00
40779620-af8e-4dbe-b483-90b32f97fe33	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.skill.admin", "resource_id": null}	2026-10-24 07:37:36.336952+00
27ef562f-7a34-400e-8979-17b7fa604a4e	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.model.list", "resource_id": null}	2026-10-24 07:37:36.489855+00
16a86bc8-316b-4eed-bf3f-8eb14d63915a	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.data_scopes.replace	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "policy_count": 36}	2026-10-24 07:37:36.633237+00
166074b8-6735-4c4b-969c-a2dbef7a6606	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	7872c65d-0ff3-4a15-95ce-39789a19ab86	success	172.18.0.1	{"code": "deerflow.project.write", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.640844+00
7b202240-d466-4a1e-befa-a4528545fc05	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	e81dfc88-8edb-4352-87b1-751beda5f0c6	success	172.18.0.1	{"code": "deerflow.thread.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.736894+00
c296a991-294b-4b24-8bbc-83445b2eeebe	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	9872643d-6d9c-489b-9339-b87db8e59659	success	172.18.0.1	{"code": "deerflow.thread.delete", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.807345+00
bf4d390f-7a5e-429e-8f9a-6cd2dde1a507	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	f10f0c43-6d8b-4b53-9271-88255609f007	success	172.18.0.1	{"code": "deerflow.run.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.898203+00
982dd08e-4978-4153-be85-3b5c66266965	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	6494dac0-c095-4397-859e-06bdf3b9207d	success	172.18.0.1	{"code": "deerflow.agent.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:33.993277+00
e0b1fa14-bc03-400c-8c3d-575d95cb19aa	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	a86721fa-348e-4347-956d-0686799fa35b	success	172.18.0.1	{"code": "deerflow.agent.delete", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.088966+00
8621f892-7fa4-413a-8ac3-53c5ca8a196e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	513c5f07-fa1c-4d87-8869-98fb4f73471a	success	172.18.0.1	{"code": "deerflow.memory.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.194421+00
6bccd018-dd2d-4d27-9bf9-819b1ee30a9e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	846cd794-54a6-4226-9b1f-459beb154d95	success	172.18.0.1	{"code": "deerflow.memory.delete", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.27646+00
ea0f4213-eee3-4fa0-9cce-d40185588ec6	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	24844308-f3d9-4e4c-a830-ad4621a03c16	success	172.18.0.1	{"code": "deerflow.channel.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.34069+00
d53b243b-52e5-4ec5-b520-a83415bf696e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	910a290c-fad1-478e-bf40-84e1f1eef0ba	success	172.18.0.1	{"code": "deerflow.channel.admin", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.405675+00
0b617f3a-67b5-4784-a0c5-bf1cd64fe2c7	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	eb9b2aaa-b7e1-42e3-9204-3e3361f00f45	success	172.18.0.1	{"code": "deerflow.integration.write", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.488089+00
8ec0690a-78bd-451d-b08a-3138d9f22f32	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	ec6d9b31-c3d8-4ff8-a1a5-caed44ba37ed	success	172.18.0.1	{"code": "deerflow.skill.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.554787+00
58da7535-8215-4d91-8ae8-d09009c27e00	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	508712af-94e0-4e20-981c-a8b50fd29d8f	success	172.18.0.1	{"code": "deerflow.skill.delete", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.627865+00
ea036131-7e85-4bab-922c-cd3242ae10ed	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	71977a98-9fc8-4957-ab52-c8bab20f80b8	success	172.18.0.1	{"code": "deerflow.subagent.read", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.688112+00
e6dfbeba-8058-48ea-8dd0-b819ad34f660	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	5a07b0cd-2329-4460-806c-deaf15fc447a	success	172.18.0.1	{"code": "deerflow.mcp.admin", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.76776+00
9c6cb127-7413-4ad6-949a-90ee28670dfb	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	aa4d3f5a-cf9b-4004-8636-bd9d68cd0268	success	172.18.0.1	{"code": "deerflow.model.invoke", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.847294+00
c59c0311-84ab-416c-b87d-c56381f71758	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	permission.create	permission	61c030cb-a174-4a05-8024-a0efc76bbb3d	success	172.18.0.1	{"code": "deerflow.sandbox.execute", "catalog_namespace": "deerflow", "application_id": "5fd4169f-b222-4864-b00a-95325083ce25"}	2026-10-24 07:37:34.922216+00
74a5c53b-ce4c-42b6-b155-8fd210195bd5	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.project.read", "resource_id": null}	2026-10-24 07:37:35.177775+00
b652e3a7-752e-4381-a4be-62ac608fef07	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.thread.write", "resource_id": null}	2026-10-24 07:37:35.350822+00
15e748ec-df31-421e-a92c-ed68af69f444	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.run.cancel", "resource_id": null}	2026-10-24 07:37:35.517661+00
9a5a39dc-2347-445c-a9a7-2dd541b8958e	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.agent.admin", "resource_id": null}	2026-10-24 07:37:35.683208+00
3d4bf2a9-4fae-4ab0-97b7-8dbf92812f87	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.memory.admin", "resource_id": null}	2026-10-24 07:37:35.880618+00
f92895e0-69f1-431a-bc54-f6f2f36b1e61	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.integration.read", "resource_id": null}	2026-10-24 07:37:36.086672+00
dca2e4b7-e648-42db-9175-fbd826cd0ed9	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.skill.write", "resource_id": null}	2026-10-24 07:37:36.266739+00
14cc635a-a2d3-4ab0-9d73-d9f11041facd	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.subagent.admin", "resource_id": null}	2026-10-24 07:37:36.41784+00
ed50dccd-e9a2-41f0-89f3-0c9f1de0a93e	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.tool.use", "resource_id": null}	2026-10-24 07:37:36.561331+00
41f0fa3d-bb31-49c0-b34d-c445654cfcac	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.preference.write", "resource_id": null}	2026-10-24 07:37:35.135077+00
c4829a27-7eaf-4558-a279-9c742cb48e5b	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.thread.read", "resource_id": null}	2026-10-24 07:37:35.312682+00
ceaf2235-977b-43e7-913b-5ae1fc9f90fb	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.run.read", "resource_id": null}	2026-10-24 07:37:35.480545+00
03a71faf-9167-4d13-b0b4-15e4e70bb0ee	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.agent.delete", "resource_id": null}	2026-10-24 07:37:35.628266+00
7d8d4587-4c46-4da7-a6f5-687de3fcd606	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.memory.delete", "resource_id": null}	2026-10-24 07:37:35.838799+00
54050f1a-92ea-4b14-8aa7-50160a5b0556	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.channel.admin", "resource_id": null}	2026-10-24 07:37:36.025145+00
b629ec16-99ac-4f7a-91f5-5bda52907513	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.skill.read", "resource_id": null}	2026-10-24 07:37:36.221434+00
5ffdf568-4ee4-429f-be93-c5ee470bd22b	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.subagent.read", "resource_id": null}	2026-10-24 07:37:36.381987+00
6f27d56c-3c8d-44e4-8849-125af5ae54c5	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.model.invoke", "resource_id": null}	2026-10-24 07:37:36.524667+00
6e4de943-afc5-4e3e-9d47-bbcb9547e257	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application.trust.change	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"trusted": true, "tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2"}	2026-10-24 07:37:36.947942+00
dcfecda1-e2fa-419a-95d2-a77f0257b9fb	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.project.write", "resource_id": null}	2026-10-24 07:37:35.235087+00
f00a8593-c2dd-4d1b-a7b9-50695ad70db4	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.thread.delete", "resource_id": null}	2026-10-24 07:37:35.390414+00
a2dfb362-455a-4118-8347-7fddba350510	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.agent.read", "resource_id": null}	2026-10-24 07:37:35.554713+00
ae174271-631f-44a3-a265-18669d6061d7	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.memory.read", "resource_id": null}	2026-10-24 07:37:35.718699+00
c9e18eab-e510-4c0a-ae84-a978dbfc3703	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.channel.read", "resource_id": null}	2026-10-24 07:37:35.920445+00
bb4ddb8a-f81c-459b-9634-249d03490136	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.integration.write", "resource_id": null}	2026-10-24 07:37:36.130513+00
ea0046a6-1f93-4ea8-adc5-07e56243539e	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.skill.delete", "resource_id": null}	2026-10-24 07:37:36.303695+00
fa04fa6e-04c7-4dd4-9b92-0ccb2a3676a6	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.mcp.admin", "resource_id": null}	2026-10-24 07:37:36.453624+00
4ff3f601-f5c5-451d-a719-175f3339b680	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.permission.grant	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"permission": "deerflow.sandbox.execute", "resource_id": null}	2026-10-24 07:37:36.596844+00
62b13313-6443-4ebc-a0fa-c317e21de238	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	user.create	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_id": "c8964ac0-0154-45fa-8062-6cedded4ab6d"}	2026-10-24 07:37:36.754661+00
1fdfefec-183e-49c1-893b-e0e1cdfe11b4	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:39:15.51802+00
07ff06b7-88c6-4a93-8a83-dd4caee234de	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:39:35.728928+00
65e5d95c-211c-43b1-8578-de4b14ca31fa	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:39:56.963591+00
352e4b05-0900-4a5a-8dec-45fd788ac6e9	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:39:57.291364+00
f350ba9f-d24f-48cb-91a2-5aaf333189e0	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:39:57.451417+00
496345c5-dc6c-45c1-8a47-72f090ff7230	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:39:57.627672+00
d5c64a3c-5636-42b1-a09c-e4fba6bce8b3	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:40:20.876261+00
96cb3200-88d7-437e-9bb5-62945486e3fb	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:40:21.187229+00
32756b54-1653-45f3-8d21-8d25585c6889	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:40:40.756043+00
85fc7898-1f1e-4b24-8aac-3f026f974265	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:40:56.835977+00
e99edfc6-5bd6-4252-a0d7-d8c4e1ffbcde	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 07:41:48.549278+00
16780014-3849-4e37-ba09-05656950c62f	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 07:41:48.75809+00
d95cafed-264e-4a70-b7f8-eb43b07d3203	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 07:41:48.882712+00
cafbe460-8cc5-45ec-ab39-c571894fd14e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:49:54.981201+00
b3d92a93-8043-41f7-894d-64caf473dea2	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:51:14.254378+00
372ae816-2ad1-4912-9587-1cd1adee0dff	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	model.create	model	922edd1b-eb38-48aa-893e-a03eca863072	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "key": "deepseek-v4"}	2026-10-24 07:51:14.524203+00
87ebf932-5a94-4d37-988c-bb3c87fbf3de	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 07:51:31.160792+00
8ff7de9c-0ab2-4d38-a575-06724a47a8db	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 07:58:01.249671+00
e73a2adf-030e-4607-a6be-4437da4d4882	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 08:19:53.302437+00
23980276-ede6-4098-8b50-b30d387a4391	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:19:53.497923+00
f677fd7a-d30b-4226-bc83-d1fbf5208830	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 08:22:40.107308+00
6c11904d-d39c-48c5-ac67-1152d3437668	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:22:40.248937+00
5ebd3400-0d14-48d8-9371-a5eb45394cc4	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:22:42.380976+00
8e439a10-d6aa-468b-84d9-1990393559ab	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 08:23:14.46762+00
82b506a5-d876-475b-b385-a9aff0d52e13	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:23:14.605245+00
0e23f9bb-972f-4a70-a1de-ef0cde56660c	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:23:16.659554+00
e7f89366-33c5-44a9-9c96-79b7668233ad	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 08:24:30.543484+00
97d6c197-4aac-4428-b833-5faac893e2c2	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 08:25:04.040513+00
3d81aa8f-a8a8-46ae-88a6-60575da2004d	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:25:04.172411+00
79a8297b-8129-4b02-9404-134cb50320f0	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:25:06.254515+00
ebb997cb-0a6f-4fd6-9b30-f8fffc969bc0	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 08:25:10.716704+00
d9204842-b78f-4c34-aea5-255396089309	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:25:12.928818+00
df6131ab-7bdb-4b44-9cb3-a8bd5cca2f0e	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:25:58.746079+00
5cf1f946-df78-4f39-a44e-4483b7a31533	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:25:13.028944+00
915d3a6a-5b6e-4d21-894d-2801f1a77dd9	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:25:35.493021+00
47eefa99-740e-4679-b807-36ffde8a92d3	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 08:25:33.323301+00
6fa6f7bf-0d78-461e-af7e-94152ad738c3	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:25:35.615323+00
a5b0e73e-39d7-4515-9c51-e85277ef3d4e	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 08:25:58.594458+00
ac696f92-0b61-4f7a-bc11-a8ea298be030	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 08:26:00.844518+00
f02431b2-09d3-4d83-b1fe-562940a72603	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 08:46:52.631121+00
360a0bbc-9bfe-4e76-8f9e-a1789fadfa1b	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 08:47:05.812318+00
4b7a3eb5-2393-4e7c-ad7c-87b15213e0b9	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 09:06:42.435809+00
0e90cf7b-66a9-47ef-a851-f4cda205c5a7	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:06:42.624267+00
44201146-7d2d-40b9-92d7-24226d7fb9bb	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:06:44.75806+00
1a8b6cdf-7d66-4d4c-9044-ccb146fbdfbc	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:06:47.370301+00
ca9660c9-f0bf-46d9-a4e7-0b2dab64955f	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 09:07:00.590613+00
2b0be0d2-ef55-423e-81a6-2c3340606a88	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 09:07:16.944124+00
0230f1e9-cb70-4051-a603-73b4455610fd	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 09:07:19.437028+00
75b2a312-8f8c-4d5c-80d6-7b42fa6faa2a	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:07:21.629908+00
5db3a561-079e-4ec6-a29a-a33b514b50c4	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:07:23.705549+00
e4886255-0785-465d-b328-51ef70e7c69b	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 09:07:58.734704+00
6fa28ad8-5d40-408c-bce1-833847c8f833	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:08:05.103466+00
72ff96e6-ff6a-40be-9097-d4782b38805c	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:08:07.205963+00
c31bfc90-e582-46aa-aa94-bc7af8eeb4b4	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 09:17:26.855619+00
e465b49d-642a-410d-95fa-209364c9659e	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 09:17:27.666693+00
676aaa49-8139-41b2-a01e-65d1040a30bf	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:17:29.965409+00
bacea6a6-5e70-49cc-89e9-f70668ca42f3	ad27a767-01c3-44be-9794-ba2e33eb2522	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:17:32.228632+00
20e51818-5892-4223-b348-b3d98ac2d20a	ad27a767-01c3-44be-9794-ba2e33eb2522	\N	auth.login	user	ad27a767-01c3-44be-9794-ba2e33eb2522	success	172.18.0.1	{}	2026-10-24 09:17:55.067948+00
73e66fed-9238-4caa-9dc4-0c17576d72c3	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 09:18:32.466773+00
3a4083c0-b245-45b7-b084-13936197813c	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 09:21:51.275887+00
99345812-7efc-4b2a-9857-53c62da27c3f	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 09:22:26.015224+00
b468c418-2220-4db7-a573-c648047ba7d1	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 09:22:52.551915+00
2ec58d4d-3429-48a6-96b0-3f4ba95bc5b2	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 09:23:07.86492+00
5adea51d-dc5e-48d9-9624-15ac22229914	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 09:23:48.577865+00
47fefe46-eb8c-4a38-920f-74a599d42c92	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 09:24:33.405356+00
2bbc43f0-4d44-4535-8dc0-63bfc97355f4	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:53:49.966243+00
57351c69-9055-4c27-ba3b-7beaf4e896ef	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:53:50.060298+00
b1b64fdb-3504-4cc8-baa5-b158879e429f	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:53:52.974633+00
2ce33d01-c68a-4dc3-a7de-2da006fb430d	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 09:53:53.016363+00
f8524ba6-c4a9-481d-9861-fc9fca19f425	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 09:55:25.494328+00
1b78cc26-e6ed-40ae-9ad1-451a35ff839d	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.bind	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_id": "c8964ac0-0154-45fa-8062-6cedded4ab6d"}	2026-10-24 09:56:48.310246+00
574fca00-221e-48c2-9e6e-4d671b2006a9	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.authorize	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 10:00:12.185788+00
93c3bbf6-bea9-4220-91ed-bd9beb523c00	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	oidc.token.exchange	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.1	{"client_id": "deerflow", "scope": "email offline_access openid profile"}	2026-10-24 10:00:12.2868+00
eecae757-9a2d-4dff-a8ad-a461fc79639c	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 10:13:05.083695+00
d4829771-f8cc-4b12-b009-bbeb6f417dc2	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 10:17:56.353447+00
27cccf9f-0759-4147-91c0-5b5956950c70	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.update	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "updated_fields": ["name"]}	2026-10-24 10:17:57.21187+00
fdfd01ec-2273-471d-9052-620fd116b3da	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 10:18:10.005515+00
45754fd6-c1f9-489d-915a-1852b3154dfc	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.update	role	c8964ac0-0154-45fa-8062-6cedded4ab6d	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "updated_fields": ["name"]}	2026-10-24 10:18:10.282129+00
51f0bd72-0c16-43f3-8893-90a624a247d0	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 10:18:31.303927+00
a4ae2d5c-63b4-436f-a2e2-e5d25b7b9ef1	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.bind	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_id": "f38cb015-416f-48b3-b4f8-97fa0c1e530e"}	2026-10-24 10:19:14.227094+00
8ef9e70d-12a9-4d8a-ade5-88493e6d48e4	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 10:22:31.512977+00
defbd426-05a6-4981-a749-85201cdb9ae2	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 10:27:09.311332+00
9205ab7d-0492-42af-b6d5-88c499ab1c59	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	denied	172.18.0.1	{}	2026-10-24 11:59:20.411541+00
8dd3d526-e553-45e9-8caa-f74aa5c7d974	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 11:59:33.430571+00
d851032b-db21-48d0-9ed9-2a15acd6dc5e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:01:54.33535+00
d7901207-e569-4851-9a63-0da9ef44b959	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:03:31.143723+00
b5b839a0-0ecf-49d0-b694-553b1c418ebc	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	user.create	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.4	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_id": null}	2026-10-24 12:06:53.285319+00
718cdc63-fa4b-4873-97f3-1765823dede6	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.bind	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.4	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_id": "f38cb015-416f-48b3-b4f8-97fa0c1e530e"}	2026-10-24 12:07:13.846701+00
1b8d139f-848e-46e3-8648-f24cc5e8dd80	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.logout	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 12:07:20.328885+00
dd705abf-c896-4a19-a46e-44340da9ccf6	8022ea54-fd44-4c71-ad61-6e52cbe95437	\N	auth.login	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	denied	172.18.0.4	{}	2026-10-24 12:07:38.608628+00
2975446f-3a0e-4bb8-be66-c9737fe2f0bf	8022ea54-fd44-4c71-ad61-6e52cbe95437	\N	auth.login	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.4	{}	2026-10-24 12:07:44.128433+00
fa9f0d10-a6a4-4609-beb7-fbe85207cc0d	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:11:14.630656+00
52389983-865f-4b96-8c4a-eab83fb6b2b2	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.bindings.replace	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_ids": ["f38cb015-416f-48b3-b4f8-97fa0c1e530e", "c8964ac0-0154-45fa-8062-6cedded4ab6d"], "role_count": 2}	2026-10-24 12:11:14.995802+00
df98b984-c34a-4185-92ab-f5dcc252818f	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.bindings.replace	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.1	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_ids": ["f38cb015-416f-48b3-b4f8-97fa0c1e530e"], "role_count": 1}	2026-10-24 12:11:15.10034+00
35facc3e-6ad9-4899-8c95-e23405da01a4	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:11:31.047774+00
85accbd3-1776-45f4-ba1a-a86973efe59f	8022ea54-fd44-4c71-ad61-6e52cbe95437	\N	auth.logout	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.4	{}	2026-10-24 12:19:26.10798+00
a41ea126-e430-4e9e-a859-810f51e3cdce	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 12:19:31.989441+00
5cb86d47-09e5-4443-adc3-4f2c18c92199	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	denied	172.18.0.1	{}	2026-10-24 12:20:43.808906+00
34a6e832-a5b9-43e7-969b-076e3952e24f	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:21:28.427045+00
9a95f62a-d9d4-4db9-bac8-2871193ca11c	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	role.bindings.replace	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.4	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_ids": ["6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac", "8d56246c-98e7-4185-8cfc-0e8c52e15d5c", "cb554b25-9993-4f6f-8335-bd08c25a3cfd", "c287b677-9d9e-4c4a-8cb0-cd82d2d27671", "f38cb015-416f-48b3-b4f8-97fa0c1e530e", "e3ae000b-f323-4c6f-838b-f5fbc1bf981c", "c8964ac0-0154-45fa-8062-6cedded4ab6d"], "role_count": 7}	2026-10-24 12:23:28.485479+00
64af9738-71e8-4adc-a8db-b246cb04c2b0	8022ea54-fd44-4c71-ad61-6e52cbe95437	\N	auth.login	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.1	{}	2026-10-24 12:24:14.38998+00
d1e286b1-12c2-42bb-9110-c646a556817d	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:25:09.728809+00
5e6b06d7-ae3f-424f-ad6f-414e4bc1645b	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:28:20.537416+00
4161e72d-9e06-419d-8f04-4a1eec8854ef	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:36:08.470066+00
133e6ed3-ecf6-4c51-a754-fbf4680d07c7	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:36:28.299032+00
18ecb111-6226-4fd9-9c7c-f3035dab7a6d	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:37:37.111971+00
4c63360b-5754-4646-820c-29f254ca2bfe	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:38:56.949216+00
50065c6f-f445-4127-bb8e-1e9a2693d897	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-24 12:39:15.185245+00
ac35b22d-1267-4a0c-b33f-927213364ca6	8022ea54-fd44-4c71-ad61-6e52cbe95437	\N	auth.login	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	denied	172.18.0.1	{}	2026-10-24 12:42:06.700741+00
84193b7e-88de-424f-93b9-ad6593f19def	8022ea54-fd44-4c71-ad61-6e52cbe95437	\N	auth.login	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.1	{}	2026-10-24 12:42:12.212269+00
b7b9942c-f47e-47a6-b0f3-0015488c20b7	8022ea54-fd44-4c71-ad61-6e52cbe95437	\N	auth.refresh	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.4	{}	2026-10-24 12:52:38.633749+00
22140167-4815-438a-811c-8dd8f03995d2	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 13:01:07.16684+00
6f6ae789-1843-4307-8565-c32fd0c109b1	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 13:01:50.473379+00
ba76cf59-d80b-4076-9458-feb7bb1dce45	8022ea54-fd44-4c71-ad61-6e52cbe95437	\N	auth.logout	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.4	{}	2026-10-24 13:02:29.339554+00
e7f02c99-e65e-4c2a-aa52-f772a7781496	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 13:02:33.134013+00
07ae7956-76cd-4e6f-b332-eb1c8a59df07	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-24 13:34:56.191206+00
0907076e-4971-4ec5-a9a6-df61abc798a0	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-27 02:22:45.696789+00
cd42ab5c-f7d4-465e-a8f6-78f7039ca181	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 03:47:09.252839+00
4b01fb9c-4043-4277-b909-54a555036461	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 06:11:08.413978+00
b961472f-7150-4b34-aa76-45791180f467	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	organization.create	organization	f660e14e-acd8-42bd-870f-2774cef9ed8e	success	172.18.0.3	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "key": "sss", "parent_id": null}	2026-10-27 06:11:55.028806+00
25379753-3d9f-44e2-9aaa-aa841d1e715b	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	organization.create	organization	c1e81dfd-32a7-49d7-b9eb-d6dcef5f0224	success	172.18.0.3	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "key": "21", "parent_id": "f660e14e-acd8-42bd-870f-2774cef9ed8e"}	2026-10-27 06:12:08.719546+00
9a285a75-400d-4a83-8679-0bcb734e2786	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	membership.organizations.replace	user	8022ea54-fd44-4c71-ad61-6e52cbe95437	success	172.18.0.3	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "organization_count": 1, "primary_organization_id": null}	2026-10-27 06:13:07.29124+00
ec3bdc39-0fe1-4131-85b4-64c0fd73fa03	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.logout	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 06:33:15.262669+00
a4ff3464-c483-4a49-a981-c25b51963e31	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 06:33:30.368542+00
0f4ab5cf-8e8e-4ec3-9fd2-064df4a7391a	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.logout	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 06:39:59.136679+00
efedcc24-51a5-4dcf-befe-8e231604c4b9	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 06:42:08.816397+00
e09911a7-456b-41b5-aff0-627f5b619f39	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.logout	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 06:53:30.680088+00
a07b86e8-a60f-4022-af49-8b51d6aca885	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 06:58:08.332041+00
7a03a070-d363-40ed-8ca6-f006a0e76e1d	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 07:30:44.749702+00
c48a0467-e5fd-4827-9926-167d594d643a	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 07:32:02.854012+00
4e58cc12-2cc7-417c-a7c4-29cafc1a76ad	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	tenant.kind.change	tenant	9c87c06c-6adf-4335-b06b-362512ec62c2	success	172.18.0.3	{"from": "organization", "to": "consumer"}	2026-10-27 07:45:24.749111+00
8d5a097a-d9f8-403d-973c-4331539ebdbc	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.logout	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 07:45:33.464632+00
e69d7812-181e-499e-a3d1-d5cf68d8812b	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 07:45:38.612015+00
56d4ef15-94a5-4bb1-a330-42d9431b1538	b16b301d-79bb-4d76-b052-bc2183409b6e	fe4a8854-cc40-451d-842a-930a3c816356	tenant.kind.change	tenant	fe4a8854-cc40-451d-842a-930a3c816356	success	172.18.0.3	{"from": "organization", "to": "consumer"}	2026-10-27 07:45:45.684458+00
5ed0e4a8-e080-4411-aced-b36d35d97a57	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 08:02:13.045667+00
6f0c44c3-2823-4e41-bc95-ebc6ad5c26df	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 08:20:24.09056+00
7f588d1e-e11d-4014-ac5b-b35e511b80d9	b16b301d-79bb-4d76-b052-bc2183409b6e	7acec14b-8ca2-4b3f-a5cd-5920142db325	tenant.create	tenant	7acec14b-8ca2-4b3f-a5cd-5920142db325	success	172.18.0.3	{"slug": "testdemo1", "kind": "organization"}	2026-10-27 08:24:19.943802+00
2b3fcafa-f74b-47fb-acb4-e7b9de12ae88	b16b301d-79bb-4d76-b052-bc2183409b6e	7acec14b-8ca2-4b3f-a5cd-5920142db325	tenant.kind.change	tenant	7acec14b-8ca2-4b3f-a5cd-5920142db325	success	172.18.0.3	{"from": "organization", "to": "consumer"}	2026-10-27 08:24:25.946521+00
df55b1b5-a990-4354-8f37-5104a04830e7	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	user_group.create	user_group	b9616803-0795-4ebd-a7f6-bcb6dd7c7fee	success	172.18.0.3	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "key": "31233123"}	2026-10-27 08:29:34.110744+00
99ba34db-1a94-4bc9-96da-e9c52d4ea6a5	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	user.invitation.create	invitation	33dd4358-5d73-4093-9cad-ee0fba40c5a0	success	172.18.0.3	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "role_id": "c8964ac0-0154-45fa-8062-6cedded4ab6d", "email": "1377@qq.com", "expires_at": "2026-10-30T08:30:27.099717+00:00"}	2026-10-27 08:30:27.079854+00
18bec9c7-61f8-4a42-ab90-d360327466d6	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 08:33:28.686528+00
493c3428-5642-4e67-be6a-a9372eeb554c	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 08:56:47.36297+00
1dccb227-4e56-4f83-b581-07deb8d8a95f	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 09:09:07.200225+00
1f99245e-978b-473b-b91a-d322b6a33468	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "275a4c2e-7001-4573-a265-7d89c918111a", "resource_type": "menu", "code": "deel"}	2026-10-27 09:24:43.633214+00
4b1eee48-852d-4401-8387-1ec484c929aa	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "25cf0585-8fcf-4734-9253-6cd6e5bb4d89", "resource_type": "menu", "code": "123"}	2026-10-27 09:25:07.545137+00
0637a833-18c0-44e3-b408-940661ee59dd	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "88209f5c-033b-43f7-82a4-a6d92f89577c", "resource_type": "button", "code": "12311"}	2026-10-27 09:25:52.904027+00
c72cded3-5e7d-4339-865c-fa318edf15ee	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.assign	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "role_id": "c8964ac0-0154-45fa-8062-6cedded4ab6d", "role_key": "deerflow_member", "resource_count": 3}	2026-10-27 09:26:13.966164+00
d3e23ff0-b3cb-4037-af5f-e2714e2cf5b5	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "fc39c8ff-672e-4cbb-8ace-f581f5a1671c", "resource_type": "menu", "code": "walkthrough.menu"}	2026-10-27 09:27:21.708562+00
a8044d42-b7e7-46bf-a4cd-fc26b56e9559	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "f235b0a1-8136-4805-9b48-0432ec9e8b39", "resource_type": "button", "code": "walkthrough.button"}	2026-10-27 09:30:03.507126+00
424c83d3-9eda-4250-ac2b-8b7b0377ee5f	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.update	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "f235b0a1-8136-4805-9b48-0432ec9e8b39", "code": "walkthrough.button"}	2026-10-27 09:30:59.105559+00
479c9202-6d88-467f-b481-68b500ba24db	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.assign	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "role_id": "c8964ac0-0154-45fa-8062-6cedded4ab6d", "role_key": "deerflow_member", "resource_count": 3}	2026-10-27 09:33:41.313283+00
80494c97-e982-4b73-9dd9-c044c34e814a	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.delete	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "f235b0a1-8136-4805-9b48-0432ec9e8b39", "code": "walkthrough.button"}	2026-10-27 09:34:28.281931+00
24d00a13-41d3-45cd-93d2-ce792913c206	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.delete	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "fc39c8ff-672e-4cbb-8ace-f581f5a1671c", "code": "walkthrough.menu"}	2026-10-27 09:35:28.382523+00
e2685937-4d6a-443a-838c-650804a49ead	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 09:39:34.189856+00
96f882f2-120d-49c8-9e1c-b692308fbfe3	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 09:42:39.886738+00
5e84a991-0fbd-4b11-b96b-60bf7dd3ad51	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "b4b8745e-dffa-4c49-91f7-479ba94b4346", "resource_type": "menu", "code": "deerflow.glyph"}	2026-10-27 09:52:15.127846+00
d1d7a825-cdaf-4274-aea8-d8e6786a141f	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "2204c167-d425-47af-a289-40e53007dee2", "resource_type": "button", "code": "deel.act"}	2026-10-27 09:54:53.965106+00
4a665c27-5228-40e0-ad64-7bc63cd660a6	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.update	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "2204c167-d425-47af-a289-40e53007dee2", "code": "deel.act"}	2026-10-27 09:56:29.264043+00
c15b9473-37fc-4e70-b51f-b54222ec44e0	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.delete	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "2204c167-d425-47af-a289-40e53007dee2", "code": "deel.act"}	2026-10-27 09:57:43.561216+00
0128e99a-1637-4ac4-abbe-d245069628b1	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.delete	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "b4b8745e-dffa-4c49-91f7-479ba94b4346", "code": "deerflow.glyph"}	2026-10-27 09:58:09.825518+00
ac0f737e-da3e-4716-9c71-f264e9e5b579	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.create	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "f573dabf-8735-43d5-b993-d138e8e9aaea", "resource_type": "menu", "code": "deerflow.final"}	2026-10-27 10:05:44.787742+00
07b9c0ee-9e17-4548-8e91-e173e39cea63	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	application_resource.delete	application	5fd4169f-b222-4864-b00a-95325083ce25	success	172.18.0.3	{"application_id": "5fd4169f-b222-4864-b00a-95325083ce25", "resource_id": "f573dabf-8735-43d5-b993-d138e8e9aaea", "code": "deerflow.final"}	2026-10-27 10:07:29.23848+00
a5ce3058-ec89-4fdd-99f4-7866dfa85ad4	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 10:09:36.611674+00
4627c3e1-f3f6-42c4-94b0-61c5e9d31c9c	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 11:25:02.131142+00
a9a94dfd-4baa-479c-b716-374f45dc95b3	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 11:29:56.915834+00
da04ff77-44a5-465a-93fa-ee37323c5544	b16b301d-79bb-4d76-b052-bc2183409b6e	9c87c06c-6adf-4335-b06b-362512ec62c2	user.invitation.revoke	invitation	33dd4358-5d73-4093-9cad-ee0fba40c5a0	success	172.18.0.3	{"tenant_id": "9c87c06c-6adf-4335-b06b-362512ec62c2", "email": "1377@qq.com"}	2026-10-27 11:37:10.680856+00
db41015a-00ca-46dc-b5bb-6c2e5148fb1f	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.logout	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 11:42:19.728464+00
daa21562-085c-429e-8e35-92a9547d0d4f	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 11:42:31.086621+00
4d7b8c02-2467-45ef-95d3-d5873a51b5db	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 11:43:54.856986+00
74376987-70e0-4468-9365-ab0873e6b837	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 11:52:36.249646+00
129a7002-33de-4fb9-b660-9e1a5cf913b3	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 11:52:53.684051+00
3fe7da06-6f7e-4b7c-8585-670360bee834	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 12:01:42.216469+00
e38c46ab-ac3b-4a89-a5a3-787d75112c8f	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 12:03:17.535152+00
dbde8c8c-f442-40fe-82ac-7f282237e577	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 12:06:24.98829+00
dee5c351-3a6f-485e-a98a-7f074faa6b05	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 12:09:10.248389+00
fd1404ab-0c86-41a1-bf22-cf3a14881681	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.3	{}	2026-10-27 12:25:07.919514+00
e3a80023-b9a3-400a-b7c3-60e1708b5d5e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 12:26:28.883972+00
7073dc1e-0953-405b-bb2b-ba0a48ef060f	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 12:28:24.303409+00
75407040-5908-4d73-932e-bf225348079c	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 12:31:44.630302+00
dd0133ac-3bbb-4d03-9c6e-a5d91ce3e10e	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 12:36:49.633042+00
175da3e8-8d5a-4823-ac49-0337314ace5b	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-27 13:08:12.749126+00
969528cc-2f07-4708-99e1-885426cef094	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-28 01:45:00.046506+00
dd8db465-713d-4b3c-8b77-596bcf1e0434	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.logout	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-28 01:49:41.323985+00
07d7680c-35ba-496a-bfd8-df4941c7fa80	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-28 01:49:43.740906+00
ed54d955-4572-4b71-a971-cdfeb07b13e8	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.logout	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-28 01:49:57.434508+00
c809a0b2-1416-4ee8-b6af-55b3242c1884	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-28 01:50:37.062751+00
3bb34c29-eab8-4690-bebf-d3cb80cf7d71	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.login	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.1	{}	2026-10-28 02:09:20.730705+00
1007a5e5-c75d-4437-9896-a08125e5f275	b16b301d-79bb-4d76-b052-bc2183409b6e	\N	auth.refresh	user	b16b301d-79bb-4d76-b052-bc2183409b6e	success	172.18.0.4	{}	2026-10-28 02:28:30.697906+00
\.


--
-- Data for Name: login_attempt_buckets; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.login_attempt_buckets (key_hash, failed_attempts, window_started_at, blocked_until, expires_at, created_at) FROM stdin;
\.


--
-- Data for Name: membership_organizations; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.membership_organizations (membership_id, organization_id, tenant_id, is_primary, created_at) FROM stdin;
7f13f993-eaf6-4c43-9fde-ac892ec275c5	c1e81dfd-32a7-49d7-b9eb-d6dcef5f0224	9c87c06c-6adf-4335-b06b-362512ec62c2	f	2026-10-27 06:13:07.29124+00
\.


--
-- Data for Name: model_catalog; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.model_catalog (id, tenant_id, key, provider, model_name, display_name, endpoint_url, credential_ref, capabilities, rpm_limit, tpm_limit, input_cost_per_million, output_cost_per_million, status, created_at) FROM stdin;
922edd1b-eb38-48aa-893e-a03eca863072	9c87c06c-6adf-4335-b06b-362512ec62c2	deepseek-v4	deepseek	deepseek-v4	DeepSeek V4 (local)	\N	\N	["chat"]	60	200000	0.000000	0.000000	active	2026-10-24 07:51:14.524203+00
\.


--
-- Data for Name: model_usage_events; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.model_usage_events (id, request_id, tenant_id, model_id, application_id, user_id, input_tokens, output_tokens, estimated_cost, outcome, usage_is_estimated, source, latency_ms, created_at) FROM stdin;
8d63612d-f89e-4f1e-ac3c-e56142709107	smoke-dd8f554b-5a87-4241-b82b-96b2ea07d9fa	9c87c06c-6adf-4335-b06b-362512ec62c2	922edd1b-eb38-48aa-893e-a03eca863072	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	10	20	0.00000000	succeeded	t	gateway	15	2026-10-24 08:25:13.515252+00
b224ff61-ec9d-4056-be29-50fa2e51d341	2818681c-9574-4855-beca-ebe8d06f8dee	9c87c06c-6adf-4335-b06b-362512ec62c2	922edd1b-eb38-48aa-893e-a03eca863072	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	8	12	0.00000000	succeeded	f	gateway	42	2026-10-24 09:17:55.274928+00
b4e3aa23-3ef7-4f10-bbd9-34c162912a6d	closeout-c83d8620-33fc-4829-b682-33bf1a2069d9	9c87c06c-6adf-4335-b06b-362512ec62c2	922edd1b-eb38-48aa-893e-a03eca863072	5fd4169f-b222-4864-b00a-95325083ce25	b16b301d-79bb-4d76-b052-bc2183409b6e	8	5	0.00000000	succeeded	f	gateway	15	2026-10-24 09:22:52.874051+00
\.


--
-- Data for Name: model_usage_reservations; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.model_usage_reservations (id, request_id, tenant_id, model_id, application_id, user_id, reserved_input_tokens, reserved_output_tokens, status, expires_at, settled_at, created_at) FROM stdin;
99feb57e-5dc8-44fe-b46f-86f43754c92c	smoke-dd8f554b-5a87-4241-b82b-96b2ea07d9fa	9c87c06c-6adf-4335-b06b-362512ec62c2	922edd1b-eb38-48aa-893e-a03eca863072	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	16	32	settled	2026-10-24 08:35:13.389289+00	2026-10-24 08:25:13.557406+00	2026-10-24 08:25:13.301546+00
d4870039-e735-4adb-8a78-d8de2b339dee	f8754031-4a71-4151-bc3b-e3c4e91e429f	9c87c06c-6adf-4335-b06b-362512ec62c2	922edd1b-eb38-48aa-893e-a03eca863072	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	10	20	reserved	2026-10-24 09:27:27.556768+00	\N	2026-10-24 09:17:27.526301+00
6d2245b2-a651-4bbc-bf6b-0297cecf6bc5	2818681c-9574-4855-beca-ebe8d06f8dee	9c87c06c-6adf-4335-b06b-362512ec62c2	922edd1b-eb38-48aa-893e-a03eca863072	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	10	20	settled	2026-10-24 09:27:55.246293+00	2026-10-24 09:17:55.288768+00	2026-10-24 09:17:55.235235+00
71673a09-b372-494d-b1c8-0879aff9d0a0	closeout-c83d8620-33fc-4829-b682-33bf1a2069d9	9c87c06c-6adf-4335-b06b-362512ec62c2	922edd1b-eb38-48aa-893e-a03eca863072	5fd4169f-b222-4864-b00a-95325083ce25	b16b301d-79bb-4d76-b052-bc2183409b6e	10	10	settled	2026-10-24 09:32:52.846448+00	2026-10-24 09:22:52.88283+00	2026-10-24 09:22:52.836095+00
\.


--
-- Data for Name: oauth_authorization_codes; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.oauth_authorization_codes (id, application_id, user_id, auth_version, membership_version, code_hash, redirect_uri, scope, nonce, code_challenge, code_challenge_method, expires_at, consumed_at, created_at) FROM stdin;
\.


--
-- Data for Name: oauth_consent_requests; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.oauth_consent_requests (id, application_id, user_id, auth_version, membership_version, ticket_hash, redirect_uri, client_state, scope, nonce, code_challenge, code_challenge_method, expires_at, consumed_at, created_at) FROM stdin;
\.


--
-- Data for Name: oauth_refresh_tokens; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.oauth_refresh_tokens (id, family_id, application_id, user_id, auth_version, membership_version, token_hash, scope, expires_at, revoked_at, replaced_by_id, created_at) FROM stdin;
0553c178-6dfc-4dd9-923a-44a9502479c6	616d987e-9bb1-428f-bed5-7c7e12602841	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	ebff00fa229b66afc276793788d56b8dcec4f1b90e0b8ce5e3fbab3b9fc6540b	email offline_access openid profile	2026-11-07 07:41:49.299475+00	\N	\N	2026-10-24 07:41:48.882712+00
5bef0ff1-8c0a-492e-a5f7-6efa33875513	dd4b8f72-9848-484b-9a07-595493f40a74	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	0c111c931348b63d7e51302ae6eb4eb04bec74ce51e1a366bd53a8415db8264d	email offline_access openid profile	2026-11-07 08:22:42.530746+00	\N	\N	2026-10-24 08:22:42.380976+00
16d0b158-b9ab-4c16-8dcd-e8424609c4d7	bef1e134-0d65-4cd0-a476-71241e2ce332	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	14c8c73cf69b8be827edda3df66162f0baa482d0eb5d3ac0e31e4cb99bc53ff8	email offline_access openid profile	2026-11-07 08:23:16.786767+00	\N	\N	2026-10-24 08:23:16.659554+00
e7410f93-a158-4be2-b6e7-e4e16cfe0431	eae8fa98-24b7-4428-8822-511d3faf518b	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	b9124d94ce7c66c3e8e6b65c0171d0b171464ba9c9ed0cbb34d575754053c7aa	email offline_access openid profile	2026-11-07 08:25:06.400716+00	\N	\N	2026-10-24 08:25:06.254515+00
886b0738-0e19-4401-882d-1df7abcce3a0	87f22592-f1f0-4458-b3f1-bf441a6eded7	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	718a11904de589e3a6ef493833bd14a0bb22a9da7358bccd073bcb86771518ab	email offline_access openid profile	2026-11-07 08:25:13.151929+00	\N	\N	2026-10-24 08:25:13.028944+00
235a2832-3876-4c33-9501-183125252bdd	56dfd13b-82da-466f-8040-0d7a4b0c647b	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	a429fa678a2542da5a637f44486a9caf0e7a11b8b52303b9a54fdc0bc02d34c9	email offline_access openid profile	2026-11-07 08:25:35.752383+00	\N	\N	2026-10-24 08:25:35.615323+00
2df413c8-eebd-430a-b880-1e376c7fb999	7b598258-96ba-41d3-bf95-2946f5c570c5	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	da68c73a226526db7805aa59ca5526d52ae86df80ed33a9c926ff1c7a81ec534	email offline_access openid profile	2026-11-07 08:26:00.973812+00	\N	\N	2026-10-24 08:26:00.844518+00
be540af0-181f-41d0-8eac-8d89bbe59a8a	538e833d-9bfe-49a0-99c2-f52f044dc014	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	7423fd45bf75cba68f09ce788d7dae63f1f8950bfb459ba9d2781e6bae47f49e	email offline_access openid profile	2026-11-07 09:06:45.130699+00	\N	\N	2026-10-24 09:06:44.75806+00
fc735cea-7d6a-40f5-98e9-67a63ca01013	befb7424-10d4-4900-95b3-f0bb2139016f	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	c00dc5554b759c28bb2a95056dbb572647c57a7ba142e4cf5ed97f63614ac4c9	email offline_access openid profile	2026-11-07 09:07:23.821339+00	\N	\N	2026-10-24 09:07:23.705549+00
d8984ada-5020-4ef8-8d67-86e4e2ccb2fd	45943d39-a837-4172-8259-8d499dfe922e	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	3562c1d7b72a0abcb59826eddd3df063bad48e6b4a6dffa0e7445166d18c88fa	email offline_access openid profile	2026-11-07 09:08:07.334152+00	\N	\N	2026-10-24 09:08:07.205963+00
9a0bf604-f7a7-4be9-87c5-e4b7c3023780	aaa4f59e-a88a-446a-91d2-fb125b2d5cbb	5fd4169f-b222-4864-b00a-95325083ce25	ad27a767-01c3-44be-9794-ba2e33eb2522	1	1	48b5c078e1704f6e90e05c1a4e7a27d1e82023209c5305249192e8ba19eb67b4	email offline_access openid profile	2026-11-07 09:17:32.621603+00	\N	\N	2026-10-24 09:17:32.228632+00
95ff0e58-bad9-465e-a276-85863397685a	4db8cc1d-44ce-427e-9bb5-313c23cf46cf	5fd4169f-b222-4864-b00a-95325083ce25	b16b301d-79bb-4d76-b052-bc2183409b6e	1	1	34005ab7922eb20ee3a2c93fe20a8881a2b78510d0bbb18aeceac11f1b00ac30	email offline_access openid profile	2026-11-07 09:53:50.405106+00	\N	\N	2026-10-24 09:53:50.060298+00
8f273bfa-05d7-442b-a9b8-540d474bc9c9	daa060e1-f9e0-4dea-8062-22296d944cd2	5fd4169f-b222-4864-b00a-95325083ce25	b16b301d-79bb-4d76-b052-bc2183409b6e	1	1	3687a8d5fedbbc26ba25e1019a3534a25b92c7aa80e89dec7ea5f07392202851	email offline_access openid profile	2026-11-07 09:53:53.159842+00	\N	\N	2026-10-24 09:53:53.016363+00
8c8771b5-ed39-418c-bf24-22ad27e14a1d	e03d6961-3398-45a6-8fc7-98cdd81bd29b	5fd4169f-b222-4864-b00a-95325083ce25	b16b301d-79bb-4d76-b052-bc2183409b6e	1	2	305d730d62d335b33563790439c1a0461d38a7773aa627b16365bbeaa5021a8b	email offline_access openid profile	2026-11-07 10:00:12.563319+00	\N	\N	2026-10-24 10:00:12.2868+00
\.


--
-- Data for Name: organizations; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.organizations (id, tenant_id, parent_id, key, name, status, created_at) FROM stdin;
f660e14e-acd8-42bd-870f-2774cef9ed8e	9c87c06c-6adf-4335-b06b-362512ec62c2	\N	sss	sss	active	2026-10-27 06:11:55.028806+00
c1e81dfd-32a7-49d7-b9eb-d6dcef5f0224	9c87c06c-6adf-4335-b06b-362512ec62c2	f660e14e-acd8-42bd-870f-2774cef9ed8e	21	刘少华	active	2026-10-27 06:12:08.719546+00
\.


--
-- Data for Name: password_reset_throttles; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.password_reset_throttles (email_hash, last_requested_at, expires_at) FROM stdin;
\.


--
-- Data for Name: password_reset_tokens; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.password_reset_tokens (id, user_id, token_hash, expires_at, consumed_at, created_at) FROM stdin;
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.permissions (id, code, catalog_namespace, resource_type, scope, description, status, surface, requires_data_scope) FROM stdin;
5a276f10-f641-44c3-911e-49eeb30b5268	iam.platform.overview.read	platform	platform	read	平台总览	active	management	f
f22381dd-18c4-4cc6-8898-227c0800cef8	iam.tenant.read	platform	tenant	read	租户列表	active	management	f
7908d053-973d-4bb3-9d3d-729b90e7b809	iam.tenant.manage	platform	tenant	manage	租户创建/启停/类型	active	management	f
867e0b7e-f8c0-4fab-a715-8e2b42019b6d	iam.user.read	platform	user	read	全局用户列表	active	management	f
f774f5e5-1cf7-47c1-b36e-6fddfe24ceda	iam.user.manage	platform	user	manage	创建用户/改状态/撤会话	active	management	f
0b9f5e4c-cc9c-472c-a614-5a6aff52a58f	iam.permission.read	platform	permission	read	权限目录读	active	management	f
cb32309e-8275-4e1a-b28e-7f60ec0a5db1	iam.permission.manage	platform	permission	manage	权限目录写/启停	active	management	f
de2e81d4-5eb3-48dd-b2ae-7cc034fe0bc1	iam.role.read	platform	role	read	角色读	active	management	f
8f1037de-e1b0-4236-bf69-5fb41be396db	iam.role.manage	platform	role	manage	角色写、绑定/解绑（平台视角）	active	management	f
9329a1d8-14cc-4f3d-9c89-eeeb2bd7643d	iam.group.read	platform	group	read	用户组读	active	management	f
a204f626-77e6-4e9d-a476-d211b44ce3ab	iam.group.manage	platform	group	manage	用户组写	active	management	f
45be6501-9f6b-4bbb-920d-3fc5107a484e	iam.member.read	platform	member	read	租户成员读	active	management	f
88ac0048-c292-4c11-8e08-bd52044394e6	iam.member.manage	platform	member	manage	成员状态/组织归属	active	management	f
85135f6c-cb27-4f84-b483-6103f2be48db	iam.organization.read	platform	organization	read	组织树读	active	management	f
493d71f1-5d0b-4816-b8be-a5bb244b8bf5	iam.organization.manage	platform	organization	manage	组织写、数据范围策略写	active	management	f
d95fe6d0-ff21-4382-95f1-20004cc55d5f	iam.application.read	platform	application	read	应用读	active	management	f
de89e761-490c-429f-928f-c405adaeadf8	iam.application.manage	platform	application	manage	应用写（非密钥）	active	management	f
731c7a90-1ffe-462c-9824-7a3f73528fdc	iam.application.secret.rotate	platform	application	manage	轮换客户端密钥	active	management	f
ecf0b8f1-ee8f-4c17-a3e2-df53f8a8576c	iam.app_role.read	platform	app_role	read	应用角色与成员读	active	management	f
d9ec0b31-e44b-459d-9a1a-22e5d545e763	iam.app_role.manage	platform	app_role	manage	应用角色 CRUD、成员 bind/unbind	active	management	f
f184b71f-9440-4508-9829-18eb2a8ae6dc	iam.app_role.assign	platform	app_role	manage	任命/撤职应用管理员（仅 key=app.admin）	active	management	f
56579e69-cb65-4324-aecc-0e94defdeea3	iam.invitation.manage	platform	invitation	manage	邀请创建/撤销	active	management	f
ddaa8759-29fc-4a1b-bde7-955c533254d9	iam.audit.read	platform	audit	read	审计查询	active	management	f
76751cb5-4ed9-473e-ae9e-e92479d8d883	iam.authorization.simulate	platform	authorization	manage	鉴权模拟	active	management	f
2dbfc849-9767-4e6e-90e2-7f014cb9e905	iam.model.read	platform	model	read	模型目录/用量读	active	management	f
df400307-7f14-45da-899c-67320517caa7	iam.model.manage	platform	model	manage	模型写/用量复核	active	management	f
b273a84a-33fa-44c5-b291-90d732815829	iam.theme.manage	platform	theme	manage	登录主题	active	management	f
4ca738d3-6966-4f08-8324-16c4480bdd88	demo.document.read	demo	document	read	演示业务码：读取文档（四级走查用）	active	business	t
e9269041-5acd-45d2-80bc-f809ca90c516	crud.document.read	crud	document	read	t	active	business	t
52eacaae-aa6d-4fdf-a33d-7b94976ca821	crud.document.create	crud	document	write	CRUD 示例：创建文档	active	business	t
9d9fa83e-c39e-4f58-8302-5ebc343b82c7	crud.document.delete	crud	document	delete	CRUD 示例：删除文档	active	business	t
1955ea73-e035-431d-a86a-be9e5c4600ea	deerflow.preference.read	deerflow	preference	read	读偏好	active	business	t
099af76d-fe81-4736-b200-898b53e65b88	deerflow.preference.write	deerflow	preference	write	写偏好	active	business	t
e94346df-56ae-494d-8ce8-af9be7d3f5a8	deerflow.project.read	deerflow	project	read	读项目	active	business	t
7872c65d-0ff3-4a15-95ce-39789a19ab86	deerflow.project.write	deerflow	project	write	写项目	active	business	t
d6271b0f-729d-49f3-b4f1-9146ea684850	deerflow.project.delete	deerflow	project	delete	删项目	active	business	t
e81dfc88-8edb-4352-87b1-751beda5f0c6	deerflow.thread.read	deerflow	thread	read	读会话	active	business	t
b58b3152-f96c-427c-8754-acb9d85bff69	deerflow.thread.write	deerflow	thread	write	写会话	active	business	t
9872643d-6d9c-489b-9339-b87db8e59659	deerflow.thread.delete	deerflow	thread	delete	删会话	active	business	t
5ea79933-3369-4020-991f-a50809571caa	deerflow.run.create	deerflow	run	create	创建运行	active	business	t
f10f0c43-6d8b-4b53-9271-88255609f007	deerflow.run.read	deerflow	run	read	读运行	active	business	t
d2bcf175-8d20-450b-a5cf-2bb73053ad11	deerflow.run.cancel	deerflow	run	cancel	取消运行	active	business	t
6494dac0-c095-4397-859e-06bdf3b9207d	deerflow.agent.read	deerflow	agent	read	读 Agent	active	business	t
6e653603-2458-4ee7-8ace-566c56dc1719	deerflow.agent.write	deerflow	agent	write	写 Agent	active	business	t
a86721fa-348e-4347-956d-0686799fa35b	deerflow.agent.delete	deerflow	agent	delete	删 Agent	active	business	t
1f025374-040d-4f76-84d3-6bf2066dbe68	deerflow.agent.admin	deerflow	agent	admin	管理 Agent	active	business	t
513c5f07-fa1c-4d87-8869-98fb4f73471a	deerflow.memory.read	deerflow	memory	read	读记忆	active	business	t
afb8e08f-ba6d-4605-8d15-86d6415d4997	deerflow.memory.write	deerflow	memory	write	写记忆	active	business	t
846cd794-54a6-4226-9b1f-459beb154d95	deerflow.memory.delete	deerflow	memory	delete	删记忆	active	business	t
74278a34-2fac-466c-b928-28b18e797f9b	deerflow.memory.admin	deerflow	memory	admin	管理记忆	active	business	t
24844308-f3d9-4e4c-a830-ad4621a03c16	deerflow.channel.read	deerflow	channel	read	读频道	active	business	t
1dc4588e-36ee-4040-af55-b31fb5c82cef	deerflow.channel.write	deerflow	channel	write	写频道	active	business	t
910a290c-fad1-478e-bf40-84e1f1eef0ba	deerflow.channel.admin	deerflow	channel	admin	管理频道	active	business	t
c333f013-4acd-47a6-a8e5-e3ca459096c5	deerflow.integration.read	deerflow	integration	read	读集成	active	business	t
eb9b2aaa-b7e1-42e3-9204-3e3361f00f45	deerflow.integration.write	deerflow	integration	write	写集成	active	business	t
8a908a46-32e9-43a4-a5b0-8cdd169a5fbf	deerflow.integration.admin	deerflow	integration	admin	管理集成	active	business	t
ec6d9b31-c3d8-4ff8-a1a5-caed44ba37ed	deerflow.skill.read	deerflow	skill	read	读 Skill	active	business	t
1eeb66f2-3ed8-46be-a555-43d8590c1d16	deerflow.skill.write	deerflow	skill	write	写 Skill	active	business	t
508712af-94e0-4e20-981c-a8b50fd29d8f	deerflow.skill.delete	deerflow	skill	delete	删 Skill	active	business	t
f72afa56-d671-472d-bb1d-d78848075e84	deerflow.skill.admin	deerflow	skill	admin	管理 Skill	active	business	t
71977a98-9fc8-4957-ab52-c8bab20f80b8	deerflow.subagent.read	deerflow	subagent	read	读子代理	active	business	t
dfbd60b6-4b24-4d03-a09b-ce210b354c7e	deerflow.subagent.admin	deerflow	subagent	admin	管理子代理	active	business	t
5a07b0cd-2329-4460-806c-deaf15fc447a	deerflow.mcp.admin	deerflow	mcp	admin	管理 MCP	active	business	t
98d380a0-0ad0-4cb7-b335-e09911444bca	deerflow.model.list	deerflow	model	list	列出模型	active	business	t
aa4d3f5a-cf9b-4004-8636-bd9d68cd0268	deerflow.model.invoke	deerflow	model	invoke	调用模型	active	business	t
61c030cb-a174-4a05-8024-a0efc76bbb3d	deerflow.sandbox.execute	deerflow	sandbox	execute	沙箱执行	active	business	t
6c69bfb4-6849-404f-9087-e7edd64bfcd1	deerflow.tool.use	deerflow	tool	use	使用工具	active	business	t
\.


--
-- Data for Name: public_registration_challenges; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.public_registration_challenges (id, application_id, email_hash, email, display_name, existing_user_id, verification_code_hash, registration_role_id, registration_role_fingerprint, terms_version, privacy_version, terms_url, privacy_url, failed_attempts, expires_at, consumed_at, created_at) FROM stdin;
\.


--
-- Data for Name: public_registration_consents; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.public_registration_consents (id, user_id, application_id, terms_version, privacy_version, terms_url, privacy_url, source_ip, accepted_at) FROM stdin;
\.


--
-- Data for Name: public_registration_email_outbox; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.public_registration_email_outbox (id, challenge_id, status, attempts, retry_after, locked_until, created_at) FROM stdin;
\.


--
-- Data for Name: public_registration_throttles; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.public_registration_throttles (bucket_hash, last_requested_at, expires_at) FROM stdin;
\.


--
-- Data for Name: refresh_sessions; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.refresh_sessions (id, user_id, token_hash, auth_version, expires_at, revoked_at, created_at) FROM stdin;
100d2f6c-400d-45d1-931a-2f3bae0382d4	b16b301d-79bb-4d76-b052-bc2183409b6e	0b0d65a8ba55faf5938c9020c9dd228a930abaeef3aab9cfdb3ea0aad405c7d6	1	2026-11-06 16:51:53.462857+00	\N	2026-10-23 16:51:53.301172+00
2aeeb56c-af4b-48d6-81de-e7a684eb90af	b16b301d-79bb-4d76-b052-bc2183409b6e	1a8c3ccafcc1bd0bb1a09de76826d24080f2e5f59ed92296a7d3b47682b5b1ea	1	2026-11-06 16:53:59.311429+00	\N	2026-10-23 16:53:59.19682+00
6a2a35eb-95b0-4dfe-bcfd-6ab0d61dff79	3d84740b-fcc5-401a-89cc-8408ccd004da	ca763f7b0a0bd6840d02c24e49d223386c66779c5ef0e8c45f05970861109836	1	2026-11-06 16:53:59.600808+00	\N	2026-10-23 16:53:59.489652+00
0f68054e-7850-40b4-b0e0-976c693d770d	08b2ecea-9232-4479-9c47-dbcd2befc0af	0b0a0d1ca629de81e82269d6b577bfc746a8f36e92012190aab88f6f4f3d7bae	1	2026-11-06 16:53:59.766989+00	\N	2026-10-23 16:53:59.65762+00
8634d3fb-6209-4b26-9e27-c68eeeaf1c9e	427efcf4-76a2-4200-8911-807d53aec55b	b35cedaadaf2c5df06579e335db2270d4374f319a4d70a76b1dd74c2dcdc4cef	1	2026-11-06 16:53:59.914318+00	\N	2026-10-23 16:53:59.8086+00
e4146690-4a3f-4bb5-b445-565635f74940	b16b301d-79bb-4d76-b052-bc2183409b6e	1aea7db0a547f117dacf5e0b2c5e79b07b618c2971f3dd0144c84e2e4eed5740	1	2026-11-06 16:54:00.090793+00	\N	2026-10-23 16:53:59.974738+00
83441884-14c6-4aaf-95a2-141454a918f1	427efcf4-76a2-4200-8911-807d53aec55b	17e006661e8c9cd7143e4244dbd9d241a69e9337a9dce1227ce75c5771c8db8f	1	2026-11-06 16:54:14.828097+00	\N	2026-10-23 16:54:14.717839+00
f8837912-1369-482b-bd9b-b1118151194b	427efcf4-76a2-4200-8911-807d53aec55b	198faac383559b56ff885e857bd0e7fa7e5f8608082cc4bcc14975bd7ffef11e	1	2026-11-06 16:54:15.074032+00	\N	2026-10-23 16:54:14.972644+00
05a4a470-281b-4fd0-80c0-fb1e3d1cd6fc	427efcf4-76a2-4200-8911-807d53aec55b	06e7c2bc6398128ea26bebdad48695e72d433855b0315318114690c04ad4e478	1	2026-11-06 16:58:00.829316+00	\N	2026-10-23 16:58:00.685594+00
915a9f10-01ae-4a82-a13e-072da7eca547	b16b301d-79bb-4d76-b052-bc2183409b6e	5e847df83f971baa02fbb0480ba98822330f0fefcd545872960adb9cdb7bdf56	1	2026-11-07 07:03:28.498319+00	\N	2026-10-24 07:03:28.409008+00
c1c7434d-e33e-49eb-91d5-c7b701268430	427efcf4-76a2-4200-8911-807d53aec55b	4ed6f6da449da8257fd01bf52660c0c36b131a2c6b43024dd75f530e9053a763	1	2026-11-07 07:03:28.790799+00	\N	2026-10-24 07:03:28.703885+00
2b68454e-a0f7-4ae2-a5c3-cf9033960c1a	b16b301d-79bb-4d76-b052-bc2183409b6e	9bc823885845dccfae112bbd578d293ac73e4845699d5f0a2f95f3d1b4158e1d	1	2026-11-07 07:20:26.774366+00	\N	2026-10-24 07:20:26.620814+00
6518856e-2d32-4fa0-8834-c750cf088fb1	b16b301d-79bb-4d76-b052-bc2183409b6e	9cae28e7abc6d39258b1b41a401efae75e304a3394c0f18c21e7a15194b3c71b	1	2026-11-07 07:20:47.393027+00	\N	2026-10-24 07:20:47.25876+00
544c18be-12a2-42b7-b985-817814cee316	b16b301d-79bb-4d76-b052-bc2183409b6e	ffd5142067184d796a6cc92202bd78880100a5260519fa9bf0375a84ba7ce26b	1	2026-11-07 07:21:04.412417+00	\N	2026-10-24 07:21:04.271127+00
13e09486-309c-4148-9af4-6b0562d455e5	b16b301d-79bb-4d76-b052-bc2183409b6e	d0bc376f2af8ed96557982cd349521860c381f0332b77066dc9290f1aa2e8735	1	2026-11-07 07:21:34.093927+00	\N	2026-10-24 07:21:33.947504+00
14b3301d-8df6-4f35-83bf-c4e98d0ea9a5	b16b301d-79bb-4d76-b052-bc2183409b6e	6f98c499c768f7e4526c5020c3a55dc11ec718a099a1a613c03d6c12ee86e6f1	1	2026-11-07 07:21:50.914386+00	\N	2026-10-24 07:21:50.774337+00
d93b873b-b027-47f1-9186-ea1ed59d2cec	b16b301d-79bb-4d76-b052-bc2183409b6e	14f43ed0ea5ac691ec5da17d85ea073c652ee1c6b3d5191e4ebcbc0ddb3569b0	1	2026-11-07 07:35:14.440976+00	\N	2026-10-24 07:35:14.293146+00
2bfddfbd-369a-4017-9f4d-10498ba4d5c1	b16b301d-79bb-4d76-b052-bc2183409b6e	d951bca1d833b413532c8ef8574f0918ab04e1fc5c80a4277e26c584cb861ffb	1	2026-11-07 07:35:32.262933+00	\N	2026-10-24 07:35:32.108888+00
5f92b999-96dc-4c72-a161-41d6c6abced7	b16b301d-79bb-4d76-b052-bc2183409b6e	585eba8b85837b65d7b81af08c666381939453c1873f778cb350d49418c50867	1	2026-11-07 07:37:33.17254+00	\N	2026-10-24 07:37:33.016185+00
e42d8222-031a-4dc8-927b-92dbe92d6cfa	ad27a767-01c3-44be-9794-ba2e33eb2522	7a2f9b0bf1b4376e4dd7eb710c7dbd6d51e8d9f6033d5730b1a86b079d11f7f5	1	2026-11-07 07:39:15.688853+00	\N	2026-10-24 07:39:15.51802+00
71b4e91f-8cb9-4cb2-9fdb-a9d6050763ad	ad27a767-01c3-44be-9794-ba2e33eb2522	ca6855edef4fe1f2175d84545661e60ebcdd2d81771f18cd09d9755f1e8b16e3	1	2026-11-07 07:39:35.866841+00	\N	2026-10-24 07:39:35.728928+00
cb702c88-9364-4157-8c45-042556639d63	b16b301d-79bb-4d76-b052-bc2183409b6e	6141147b5be92ae6771aa7f5a457b485ffb3286767d4ed334ece7d532da78970	1	2026-11-07 07:39:57.110952+00	\N	2026-10-24 07:39:56.963591+00
c86a9e7e-a53a-4d76-b0fc-bd0fe48f42a4	ad27a767-01c3-44be-9794-ba2e33eb2522	8ae3ec3fdea4fde23f80b5a07f3f620da412083a9b6435756b7705a699e0d289	1	2026-11-07 07:39:57.423348+00	\N	2026-10-24 07:39:57.291364+00
9e538e7e-9924-44e8-beb4-75544772766c	ad27a767-01c3-44be-9794-ba2e33eb2522	e2890a853ea3d4706f85f27ab10aadf69eb533fff5865ab29e296c70ad3e8d9c	1	2026-11-07 07:39:57.596072+00	\N	2026-10-24 07:39:57.451417+00
32657105-c7d8-4d6d-8c55-4c073ec7c2a4	ad27a767-01c3-44be-9794-ba2e33eb2522	025d8d4645b8998740b2536e34aa1c76e8ed5b953737923f591a89cee438a0c6	1	2026-11-07 07:39:57.76114+00	\N	2026-10-24 07:39:57.627672+00
dbb9b134-a161-4216-9247-4013dfedbeeb	ad27a767-01c3-44be-9794-ba2e33eb2522	2a485c4a28853e6c0ba944d266f1904bc616ce38109d18e43a33853526d08131	1	2026-11-07 07:40:21.020246+00	\N	2026-10-24 07:40:20.876261+00
c47420af-a773-474e-aea9-b354e325b485	b16b301d-79bb-4d76-b052-bc2183409b6e	eb2fbd53a2bc5c9abfad9e6b7947cfebbfca91951b2b3361c6cc1ec47535a8f6	1	2026-11-07 07:40:21.322401+00	\N	2026-10-24 07:40:21.187229+00
7647faab-3feb-42c0-8b4b-2efb5a812869	ad27a767-01c3-44be-9794-ba2e33eb2522	c5abecbf52e842335ad0fa7e17507b0197ac2c81e1c10f297fb4611b8bc9a1bd	1	2026-11-07 07:40:40.89901+00	\N	2026-10-24 07:40:40.756043+00
2a65c64c-300e-464b-ae01-7ce5bd710220	ad27a767-01c3-44be-9794-ba2e33eb2522	67e5755b6419487638c2f47fd28fbe9640b96de810453905d43308439ea88c00	1	2026-11-07 07:40:56.980332+00	\N	2026-10-24 07:40:56.835977+00
91f516d7-806a-47e4-bc46-d9172479f577	ad27a767-01c3-44be-9794-ba2e33eb2522	085a91c9161027c4b903c21e6f2ce153eef47b11c5593624cffae389f3dfcc2d	1	2026-11-07 07:41:48.725462+00	\N	2026-10-24 07:41:48.549278+00
4a815480-923c-45c9-8f1d-dac962db3c0b	b16b301d-79bb-4d76-b052-bc2183409b6e	fff9d7f71bbd704325be088aca75143d4068a425d03a1622aff14e1f26614633	1	2026-11-07 07:49:55.148208+00	\N	2026-10-24 07:49:54.981201+00
c0677391-8775-4b30-b1b0-13e0bd8f6767	b16b301d-79bb-4d76-b052-bc2183409b6e	22dea249b4e9dfcd14dc5ca179f7842e7d81003e891621b9c0c9394c24dbf721	1	2026-11-07 07:51:14.401486+00	\N	2026-10-24 07:51:14.254378+00
e88b6b3f-0562-4fe1-ace9-59142f10f9c8	b16b301d-79bb-4d76-b052-bc2183409b6e	7d478620b606ac205dbc5b36e95c834b74b2e28661839a1e7920d434ce47e37f	1	2026-11-07 07:51:31.3226+00	\N	2026-10-24 07:51:31.160792+00
0f6936fc-eb95-4dfc-9139-21a754e325d8	ad27a767-01c3-44be-9794-ba2e33eb2522	b7fcb86b6a02b6f561570e88a00a959c226a066172289a99309c12e59377eb3a	1	2026-11-07 08:19:53.445051+00	\N	2026-10-24 08:19:53.302437+00
ebeb5eac-ba84-4e4b-9ac5-07ce16326933	ad27a767-01c3-44be-9794-ba2e33eb2522	ceb4260d32b3177a3045b588b4ea0c9c4fd04e1e639bf05f33b4b4d4a661c576	1	2026-11-07 08:22:40.219443+00	\N	2026-10-24 08:22:40.107308+00
2e5eb243-38f8-4327-995b-e4e5609dccc9	ad27a767-01c3-44be-9794-ba2e33eb2522	f3c352ab01c2aa771421fa7112a7a9d3ceb471d9d25f2aba16f033e2d71312b5	1	2026-11-07 08:23:14.57385+00	\N	2026-10-24 08:23:14.46762+00
75f8afc5-0185-4cae-b6c0-b3db77dbc6d1	b16b301d-79bb-4d76-b052-bc2183409b6e	34825488a0b215f119786df12ae72e6eb9ff9f453202c8356d10d6629a60f872	1	2026-11-07 08:24:30.658537+00	\N	2026-10-24 08:24:30.543484+00
58435a16-f75e-4d9f-8fec-24ab09fdb689	ad27a767-01c3-44be-9794-ba2e33eb2522	b3140730ce06d9379b8fa6763ada8ad8c6f08587c3e72aa141c15c5b8ec285cf	1	2026-11-07 08:25:04.152078+00	\N	2026-10-24 08:25:04.040513+00
effb763e-b145-44c2-b887-092016b752ee	ad27a767-01c3-44be-9794-ba2e33eb2522	eab4db7b34589c624821d1c9e84d008c10e78cae49af858728c725ac360d4249	1	2026-11-07 08:25:10.844721+00	\N	2026-10-24 08:25:10.716704+00
f1b0bd0c-b402-4f1f-8dc4-3721caf04931	ad27a767-01c3-44be-9794-ba2e33eb2522	6c2f18030ea2110cd719a7234660c0e7eb91c86bce7a887c213e72008b6ef719	1	2026-11-07 08:25:33.43146+00	\N	2026-10-24 08:25:33.323301+00
88b7151a-bcaf-4fd7-b3c3-ea41403f186d	ad27a767-01c3-44be-9794-ba2e33eb2522	712814a732aa5ac333d745147ddb394c5aed1478a1b53f9a927881bed6a0d54d	1	2026-11-07 08:25:58.719753+00	\N	2026-10-24 08:25:58.594458+00
f62de8c8-9c50-4d3b-8dfa-1ec2abd5bdd0	b16b301d-79bb-4d76-b052-bc2183409b6e	c2c80a29e95509d853347ed27ffb7c78377199ffa929df9f19b54186d23c9ccf	1	2026-11-07 08:46:52.757573+00	\N	2026-10-24 08:46:52.631121+00
b36d4858-14e4-4e3a-872e-efbc09ff8d62	b16b301d-79bb-4d76-b052-bc2183409b6e	1994104f845735b452f8e9b25f218d2a59b4f0ce07419b3c8492e7c33020653c	1	2026-11-07 08:47:05.923494+00	\N	2026-10-24 08:47:05.812318+00
ec800585-f269-484f-8c9b-3d9c68445e7e	ad27a767-01c3-44be-9794-ba2e33eb2522	68e94fd1bd69d145728f4faea60c43f2aa64e59d5adfa487c993e080ccbd800d	1	2026-11-07 09:06:42.566432+00	\N	2026-10-24 09:06:42.435809+00
ba9e77a8-d56f-4028-b68c-f1e4ac61d731	ad27a767-01c3-44be-9794-ba2e33eb2522	4a8d0aa4d56d301b5bb571fba151b94ef5a6f45bb900106cc71afd560fb67f2f	1	2026-11-07 09:07:00.699716+00	\N	2026-10-24 09:07:00.590613+00
0e286242-66ab-4caa-a5f5-e3eef564eeb6	ad27a767-01c3-44be-9794-ba2e33eb2522	d6b0e8808a2560476ead91446ac26962aa75b5588cb40175c28b9921ebe61d35	1	2026-11-07 09:07:17.053268+00	\N	2026-10-24 09:07:16.944124+00
3d858870-fcf1-4700-b2d9-05e00828b86d	ad27a767-01c3-44be-9794-ba2e33eb2522	57c021453c3a409a3a2cd253d67ad8fb798623f21e213c95167789d9cb47b320	1	2026-11-07 09:07:19.543923+00	\N	2026-10-24 09:07:19.437028+00
4921181a-ef80-423a-bee6-937925cfcc52	ad27a767-01c3-44be-9794-ba2e33eb2522	3575b4715f25f7e3f39cf36deb85bbc427115f5280666cfcdb83562b9a29e977	1	2026-11-07 09:07:58.846902+00	\N	2026-10-24 09:07:58.734704+00
78da06de-216d-4142-aaa9-977c40c57e12	ad27a767-01c3-44be-9794-ba2e33eb2522	c6c86de7e17ce6f28a780143eba70bc07658b47dd0ac72345c81d14fdcf41343	1	2026-11-07 09:17:26.99541+00	\N	2026-10-24 09:17:26.855619+00
86af433c-9a55-448e-96f8-73e80e8cfd99	ad27a767-01c3-44be-9794-ba2e33eb2522	c712288ca976b5f3620492fbfed09f1d33d2131c077f157894e6b78c49741837	1	2026-11-07 09:17:27.77492+00	\N	2026-10-24 09:17:27.666693+00
fa9addfd-65bd-4d6b-8960-22a7f7792d7c	ad27a767-01c3-44be-9794-ba2e33eb2522	f8838dcb2062b0c143527f1cfb3571de247ba5f16d7aa2cc88e06efa3e64afe8	1	2026-11-07 09:17:55.175269+00	\N	2026-10-24 09:17:55.067948+00
a73005eb-5fe3-4cf1-846e-ae3d5dfb1471	b16b301d-79bb-4d76-b052-bc2183409b6e	dca7cfcdcba798ef81f52bd250387a37bcc5a3bbb7746c3e3f96807e017bf446	1	2026-11-07 09:18:32.588898+00	\N	2026-10-24 09:18:32.466773+00
be43cab6-3715-4ff1-93d7-eeb99576d2cd	b16b301d-79bb-4d76-b052-bc2183409b6e	0659095f9b32bdce5aed51b05b250c3aa09de3d199273338e5d968d35dc3cc96	1	2026-11-07 09:21:51.40199+00	\N	2026-10-24 09:21:51.275887+00
13ad0c57-8e0d-48b1-bf55-a2994212aa21	b16b301d-79bb-4d76-b052-bc2183409b6e	3f285481d90caa3e2e4764d2c5abda8f9fa0cd407960cabf6a3dd6b6c3317d88	1	2026-11-07 09:22:26.138586+00	\N	2026-10-24 09:22:26.015224+00
48737482-87bd-4bc1-a3b5-953dfcd91b9c	b16b301d-79bb-4d76-b052-bc2183409b6e	6770204613751ab5f64ecbbb2aa42aeeef382ceabd6af4de9de8f6f673aac965	1	2026-11-07 09:22:52.668848+00	\N	2026-10-24 09:22:52.551915+00
3b6dd285-3888-4490-a096-e91dd8862319	b16b301d-79bb-4d76-b052-bc2183409b6e	d3227af25f66d3eb0a6f4251a082efac0698ac4ad5b095ca326a9364ef564049	1	2026-11-10 12:26:29.111741+00	\N	2026-10-27 12:26:28.883972+00
23b7fb4d-c515-4209-9402-0314d983a7aa	b16b301d-79bb-4d76-b052-bc2183409b6e	7ac92672ae77aa6a2802c63d42b625663d42fd9cb346fff0ce66e6bc0a6bc224	1	2026-11-11 01:45:00.175037+00	2026-10-28 01:49:41.336639+00	2026-10-28 01:45:00.046506+00
082fbb48-a1ac-4e49-b69d-0e288d7f55fd	b16b301d-79bb-4d76-b052-bc2183409b6e	1a2941de1f365bd2f6a124ad3e7add3e969accea82a587d4a5846f8f366dad8f	1	2026-11-11 02:09:20.896716+00	\N	2026-10-28 02:09:20.730705+00
078e78e5-64e0-47db-94cd-00e5542b374b	b16b301d-79bb-4d76-b052-bc2183409b6e	9229f6177fbefb0872b45994e3c82e0ecdf2fa3ec9e073b1c757c863b2a93f1c	1	2026-11-11 01:50:37.189325+00	\N	2026-10-28 01:50:37.062751+00
ef2f105c-d079-44ea-8b7d-6a6a310fdefa	b16b301d-79bb-4d76-b052-bc2183409b6e	3e0e4620d80010de6548f32968f314b385b278fd12e2d17d3fe2f787dbae0f5a	1	2026-11-07 09:23:07.974463+00	\N	2026-10-24 09:23:07.86492+00
0c8d018b-d8c6-4ff2-9815-ab3bfd2bcb49	b16b301d-79bb-4d76-b052-bc2183409b6e	7d1e5b4a01803f89a085d9c03dc423ae4e716bf14c7139afaa5d167b20517fde	1	2026-11-07 09:23:48.685553+00	\N	2026-10-24 09:23:48.577865+00
dc7068c9-a106-4817-83b6-f89c75f36ab4	b16b301d-79bb-4d76-b052-bc2183409b6e	e891e41cbc126d473dcb1cb5f328fd4391206b8925406153088d47fbb440dd81	1	2026-11-07 09:24:33.515957+00	\N	2026-10-24 09:24:33.405356+00
b40f697d-164f-482c-bd82-0d9f0f48ddaa	b16b301d-79bb-4d76-b052-bc2183409b6e	3b7bdbfb3913fcc4418c7181e6cd0d32bdecc435948afb5a32257e8428a627c5	1	2026-11-10 12:25:08.132325+00	\N	2026-10-27 12:25:07.919514+00
8658524e-4d4a-482d-8c17-cc30e4090883	b16b301d-79bb-4d76-b052-bc2183409b6e	0515b7203cea929bfcf8154bc42d27b10f3fb69c6ba875a864a2ed8e367c03e3	1	2026-11-07 10:13:05.429729+00	\N	2026-10-24 10:13:05.083695+00
81845928-9645-42f3-a703-bb498b145628	b16b301d-79bb-4d76-b052-bc2183409b6e	a5001e47d38a598131c5bf5015026c13feedb2820d8c58f1883446f1f73a2f47	1	2026-11-07 10:17:56.515068+00	\N	2026-10-24 10:17:56.353447+00
2c655b06-2a01-484e-968e-5516c8ffbe7b	b16b301d-79bb-4d76-b052-bc2183409b6e	c756c161fa670b90d347ab40f8a8e420e86e17de612589fd86d15a52fc3bf0db	1	2026-11-07 10:18:10.182154+00	\N	2026-10-24 10:18:10.005515+00
34457bfa-d871-419c-a783-346b8260fcb9	b16b301d-79bb-4d76-b052-bc2183409b6e	15b442c186dae7c246ad1254506c8d9ca7716c9ed3f891da5283a8b15a5997dd	1	2026-11-07 10:18:31.511136+00	\N	2026-10-24 10:18:31.303927+00
e8cf9686-4824-486a-8d28-6c9ad79c8035	b16b301d-79bb-4d76-b052-bc2183409b6e	541737758e5cf46a367ccce874ea135625917fbf42790e68b635493ce5b9bb7e	1	2026-11-07 10:22:31.657952+00	\N	2026-10-24 10:22:31.512977+00
3dc0a6c9-5b83-4e52-961b-8c2926491384	b16b301d-79bb-4d76-b052-bc2183409b6e	4c1b92b0b0a745a6c62491a85ba9438f48edf261729fe75f6ae31e7c0205562a	1	2026-11-10 12:28:24.483321+00	\N	2026-10-27 12:28:24.303409+00
0641e06e-6ca9-4103-ab67-222b01bfaf06	b16b301d-79bb-4d76-b052-bc2183409b6e	e5aed13b38565be8c49bc343bf22cc62dbef82912c7575d3a61aa19baad38019	1	2026-11-06 16:29:59.00057+00	\N	2026-10-23 16:29:58.873307+00
c96ccb03-f044-40d3-9334-505c61557c43	b16b301d-79bb-4d76-b052-bc2183409b6e	307c83679b61f5a1c937430d69b7b1b2508151e9d8e8556951171e997661a411	1	2026-11-07 12:01:54.475175+00	\N	2026-10-24 12:01:54.33535+00
4e75d719-856f-4a2a-b1f3-533b8546cacc	b16b301d-79bb-4d76-b052-bc2183409b6e	6c5533eb86c0e2dbb6b74190c87bf0a43acd40235ab3dc415b2ee8beda7e83ce	1	2026-11-07 12:03:31.359925+00	2026-10-24 12:07:20.357764+00	2026-10-24 12:03:31.143723+00
ea3e8e64-0c33-440d-9f2c-a8db54d6241d	b16b301d-79bb-4d76-b052-bc2183409b6e	a6d23fe2c112294e1cd52942985ad773bc96c9a7a530fe4652f131cf8c5d0238	1	2026-11-07 12:11:14.758072+00	\N	2026-10-24 12:11:14.630656+00
f8dca18f-b352-49f6-bfba-3f9654a1de17	b16b301d-79bb-4d76-b052-bc2183409b6e	3e9a98d148a4750bba0c3ba03aa26d0d3ad45b0f248c5fb9b3b1f96d9b45c9bc	1	2026-11-07 12:11:31.160648+00	\N	2026-10-24 12:11:31.047774+00
58771bf1-491f-4343-bfe4-2a7452b86b70	8022ea54-fd44-4c71-ad61-6e52cbe95437	bd1f34e014b86dfc9895b8adda20871351d50e3f946bfd1f1c739f78757e7ff8	1	2026-11-07 12:07:44.300875+00	2026-10-24 12:19:26.12324+00	2026-10-24 12:07:44.128433+00
176ae167-287b-4535-b39b-0eea80491526	b16b301d-79bb-4d76-b052-bc2183409b6e	20d1e2846bf528afde5edf93d08d127fca522d9aad05fd302caeb302c139fb3e	1	2026-11-07 12:19:32.145382+00	\N	2026-10-24 12:19:31.989441+00
9b7c8f32-092d-4bff-882e-d36f57eda4db	b16b301d-79bb-4d76-b052-bc2183409b6e	f61d76df1bd37eea1ae2805418db1b955405eb60effe92561b31a0c485beb1ff	1	2026-11-07 12:21:28.580379+00	\N	2026-10-24 12:21:28.427045+00
3c182901-f7da-4906-b8af-b4775a97d718	8022ea54-fd44-4c71-ad61-6e52cbe95437	70bbb35e34f5f02f8573a75609319c3e5e33b14e98c7d3216ab7c6506fdf1e3c	1	2026-11-07 12:24:14.543791+00	\N	2026-10-24 12:24:14.38998+00
88f45a10-dc17-4a8f-9713-743d9c314510	b16b301d-79bb-4d76-b052-bc2183409b6e	4a2733f4946a68c3732da435ae6bdae74b5c926569ae8d02b11408b734b610ac	1	2026-11-07 12:25:09.88515+00	\N	2026-10-24 12:25:09.728809+00
4ed46a5a-71ae-4528-9a7a-9825fa8414ed	b16b301d-79bb-4d76-b052-bc2183409b6e	f26f4795884ce480fea742e58c55cdaeb42e29e43220e0813efd8e60481ea8a9	1	2026-11-07 12:28:20.686912+00	\N	2026-10-24 12:28:20.537416+00
e772a85f-2e5c-4f15-9d17-d6fd005cd3df	b16b301d-79bb-4d76-b052-bc2183409b6e	95b41aa5290d94da0db3317b0550ace2e929c4c19a3683c408562722a4eb3fb8	1	2026-11-07 12:36:08.62056+00	\N	2026-10-24 12:36:08.470066+00
dc205434-c4c4-4238-9cc5-f71d8ed707c2	b16b301d-79bb-4d76-b052-bc2183409b6e	5a87645ece9b76ad0f54e6919927d43a8032a0501840f67bbddeaae7345e1a0b	1	2026-11-07 12:36:28.404174+00	\N	2026-10-24 12:36:28.299032+00
5affe9a6-82b4-4d7b-ab8c-3de896338c91	b16b301d-79bb-4d76-b052-bc2183409b6e	8f09f7a252ee69ada0d74208f18e3d09d527e4f8951d728bd9f6e4ad6239e3ad	1	2026-11-07 12:37:37.23692+00	\N	2026-10-24 12:37:37.111971+00
affefed9-4620-443c-93cc-c07d9306d356	b16b301d-79bb-4d76-b052-bc2183409b6e	60d7e0ff13ac7e6b19d8da9f6eb51d55562a85b504cb00d77a066bd6d28dab3b	1	2026-11-07 12:38:57.060779+00	\N	2026-10-24 12:38:56.949216+00
b76ab465-c817-4c36-8a36-cc32fe7bb9be	b16b301d-79bb-4d76-b052-bc2183409b6e	a775f9d6a961506dda21dffb9549526c66cde605dd879b7202c7d0e913431450	1	2026-11-07 12:39:15.331664+00	\N	2026-10-24 12:39:15.185245+00
0d299c6c-c473-440f-ba87-330f2830cce9	b16b301d-79bb-4d76-b052-bc2183409b6e	b0d863d0e24eb8a9f0e60fba86276f29d786344d638905902b2fd7b0698b4ebf	1	2026-11-10 12:31:44.766867+00	\N	2026-10-27 12:31:44.630302+00
3ae60120-fc76-4629-a4b0-798f5e04a31c	b16b301d-79bb-4d76-b052-bc2183409b6e	7aad80479f0b62749e68afe9a11160c153f187a726ebdea903086f052e2780df	1	2026-11-07 13:01:07.396838+00	\N	2026-10-24 13:01:07.16684+00
99ee9e43-7503-42f9-8145-55ba1064301d	b16b301d-79bb-4d76-b052-bc2183409b6e	f7b7a6f6f3450b929297967e5da667883b741b435cdea3c91e77ebafddf76c5d	1	2026-11-07 13:01:50.709677+00	\N	2026-10-24 13:01:50.473379+00
37256621-8c40-4f8b-924d-22e55f62c158	8022ea54-fd44-4c71-ad61-6e52cbe95437	67bef1692fc8a45d6e7cd6effa0b3a6d2ac769cf98c3aebdf6c7618e6ab581dd	1	2026-11-07 12:42:12.358113+00	2026-10-24 13:02:29.377951+00	2026-10-24 12:42:12.212269+00
2ccda656-093c-41de-9693-cf537f2936db	b16b301d-79bb-4d76-b052-bc2183409b6e	586fe7bd4a29bc5955708e6f7f957b2134d743765e476d0907941bb3cb729860	1	2026-11-07 13:02:33.309712+00	\N	2026-10-24 13:02:33.134013+00
24d98771-16d6-4a78-af5e-3c5f459675dd	b16b301d-79bb-4d76-b052-bc2183409b6e	b3e248aa4fe552c9513bbac9948cd843ca9ed6c55285a36756a8d7840a1d7665	1	2026-11-10 02:22:45.857788+00	\N	2026-10-27 02:22:45.696789+00
e282646d-4b51-4568-b48f-d03d4a144116	b16b301d-79bb-4d76-b052-bc2183409b6e	3e123472228c52b59814b0ef9ea1ade89b56b4fd60f631f33c52b091810b115a	1	2026-11-10 03:47:09.423796+00	\N	2026-10-27 03:47:09.252839+00
2e67dd67-228d-48a4-9af4-da1862a12b5d	b16b301d-79bb-4d76-b052-bc2183409b6e	22dc91950955acf971000a98205c15e360481c51f0eac6f0042c062c613297ed	1	2026-11-10 06:11:08.567223+00	2026-10-27 06:33:15.277301+00	2026-10-27 06:11:08.413978+00
395a6dda-638e-454b-8894-75264afb1e90	b16b301d-79bb-4d76-b052-bc2183409b6e	9025b616b16b4f790f7b409331fb7127886fc1d8b31107c31696b78075e6698f	1	2026-11-10 06:33:30.492182+00	2026-10-27 06:39:59.145844+00	2026-10-27 06:33:30.368542+00
9cee9d8e-d3c3-4a51-8c27-8c06cb723264	b16b301d-79bb-4d76-b052-bc2183409b6e	9e7ba6bf451407c20fdb6494c8b9cf67aa468b2ff84b7670c286fa258cc2464e	1	2026-11-10 06:42:08.932265+00	2026-10-27 06:53:30.689181+00	2026-10-27 06:42:08.816397+00
c6a32c35-d5b8-4561-8764-fd69e2eef801	b16b301d-79bb-4d76-b052-bc2183409b6e	830b452d6e5d2a667cc30d062d9cc28036cc24091d8991826035d816b000b3a7	1	2026-11-10 12:06:25.134854+00	\N	2026-10-27 12:06:24.98829+00
aedb4fa0-9f73-402a-92a1-0387b94b0fe1	b16b301d-79bb-4d76-b052-bc2183409b6e	d8c9193e22dcc6f51738eb03372e7501d9ceb9ffa76c4b24cc10f320c778d000	1	2026-11-10 07:30:44.881884+00	2026-10-27 07:45:33.475813+00	2026-10-27 07:30:44.749702+00
ffda99d8-1d23-431c-8dd4-1291783001a8	b16b301d-79bb-4d76-b052-bc2183409b6e	cd91996127b2ee1a26bb7330e9d64b055c0a5385c808d98a0cd4559a1eff4506	1	2026-11-11 01:49:43.854349+00	2026-10-28 01:49:57.447896+00	2026-10-28 01:49:43.740906+00
83e8c86e-cae6-455e-a79f-8a8437f3e70d	b16b301d-79bb-4d76-b052-bc2183409b6e	76dfe7a7949ee002b73c91e329a0d2739655cafc736d27e62435c3d3b6462db5	1	2026-11-10 11:43:54.993091+00	\N	2026-10-27 11:43:54.856986+00
03ed90cd-fbdd-41f3-bead-f2bb2260b433	b16b301d-79bb-4d76-b052-bc2183409b6e	cc14ad56ef9d905069acfd158d4f4a88fd4372af4d48fc05e72329b0321be877	1	2026-11-10 11:52:36.376212+00	\N	2026-10-27 11:52:36.249646+00
e18e1262-85d9-41fe-96b8-798fee4a8d96	b16b301d-79bb-4d76-b052-bc2183409b6e	a25ec45e134fef7bca6fa77e7f38055dbb08a79fd6a7c0391ff3f72403ab2fa7	1	2026-11-10 06:58:08.494466+00	\N	2026-10-27 06:58:08.332041+00
e2421c8f-9fe6-4ab5-9987-6c090e6ab762	b16b301d-79bb-4d76-b052-bc2183409b6e	6d7817ac9f8cb0758e036841c2eb3e4da711c21fc3b2c2e05aab14c11e7d7fae	1	2026-11-10 07:45:38.789442+00	2026-10-27 11:42:19.742303+00	2026-10-27 07:45:38.612015+00
da412c92-dbf9-434c-b332-0735f2fa209b	b16b301d-79bb-4d76-b052-bc2183409b6e	8df62702e116efeafd43e5a824f577f98757d3180368cb601236847d9a074fb2	1	2026-11-10 11:42:31.237765+00	\N	2026-10-27 11:42:31.086621+00
f7306602-a25c-4887-8edf-2a73b3cbdff8	b16b301d-79bb-4d76-b052-bc2183409b6e	94da3d1649f25df3c0ba12a089d99741f04644bb73cc77bb6fbd9feaa1636346	1	2026-11-10 11:52:53.814632+00	\N	2026-10-27 11:52:53.684051+00
7bd9792d-0005-4688-8cd8-4b7d991faaee	b16b301d-79bb-4d76-b052-bc2183409b6e	f48943617fd260664afd8e0f787cca1baf8e43e436e08328de9006ac1c5edda9	1	2026-11-10 12:01:42.38261+00	\N	2026-10-27 12:01:42.216469+00
9943f3bd-57fa-430d-b02b-c5c3e1969181	b16b301d-79bb-4d76-b052-bc2183409b6e	a99697f2f4a1ebeb489decc3e33b6f33354698b7f5cc72691978702f637935c7	1	2026-11-10 12:03:17.686599+00	\N	2026-10-27 12:03:17.535152+00
c725395a-568b-4955-b54d-70532385e529	b16b301d-79bb-4d76-b052-bc2183409b6e	74b0a32f69d419d3742f192988bfd23d1c9a3836aa7aa1d7b36fb4fd70e97147	1	2026-11-10 12:09:10.386419+00	\N	2026-10-27 12:09:10.248389+00
\.


--
-- Data for Name: revoked_access_tokens; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.revoked_access_tokens (jti_hash, token_use, expires_at, revoked_at) FROM stdin;
\.


--
-- Data for Name: role_application_resources; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.role_application_resources (role_id, resource_id, created_at) FROM stdin;
c8964ac0-0154-45fa-8062-6cedded4ab6d	275a4c2e-7001-4573-a265-7d89c918111a	2026-10-27 09:26:13.966164+00
c8964ac0-0154-45fa-8062-6cedded4ab6d	88209f5c-033b-43f7-82a4-a6d92f89577c	2026-10-27 09:26:13.966164+00
c8964ac0-0154-45fa-8062-6cedded4ab6d	25cf0585-8fcf-4734-9253-6cd6e5bb4d89	2026-10-27 09:26:13.966164+00
\.


--
-- Data for Name: role_bindings; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.role_bindings (id, membership_id, role_id, created_at) FROM stdin;
92f54711-a678-459d-b031-6d204029e7b8	4da8e011-9248-4378-9d6c-16e0cd620017	7fbd7166-1f58-44f6-bf3e-102ad7687666	2026-10-23 16:26:39.234987+00
3e0d7516-4ec3-476c-bf9b-fd79ab2dbbe3	44bfe126-3bf3-4d17-9ebd-4e39d054171a	96aceeb3-6270-4a8d-ac35-f80e90363142	2026-10-23 16:53:14.473478+00
c3017d14-ded7-496b-82f8-18f484637f58	db238b0d-7e28-4ec0-9726-e34994a670fe	f4a857ce-150c-4163-a628-0d844d30d788	2026-10-23 16:53:14.473478+00
9683e5b9-2cf7-4908-9410-fb15ead3aa8d	52dc0ceb-26eb-4db3-8221-7fa416e5a7ca	3cf6d506-9ce1-41cc-950c-5623e4c896d1	2026-10-23 16:53:14.473478+00
22f1c7aa-a3e7-4f42-a3ee-ac7bad367c93	700f02fb-aa59-4f02-babc-bd0697122770	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	2026-10-24 07:21:51.645196+00
d888e5ce-cd7c-47e6-9690-875ae5e819ea	a9cb2c45-b92a-4484-9597-b4a1de950f37	c8964ac0-0154-45fa-8062-6cedded4ab6d	2026-10-24 07:37:36.754661+00
33d64ab9-88d0-44b8-8bd3-b7c368575d66	4da8e011-9248-4378-9d6c-16e0cd620017	c8964ac0-0154-45fa-8062-6cedded4ab6d	2026-10-24 09:56:48.310246+00
477ca7d0-48bb-4329-bdee-f58dbf95c324	4da8e011-9248-4378-9d6c-16e0cd620017	f38cb015-416f-48b3-b4f8-97fa0c1e530e	2026-10-24 10:19:14.227094+00
e40f27dc-ce06-4e67-8da9-e33f90a96d19	7f13f993-eaf6-4c43-9fde-ac892ec275c5	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	2026-10-24 12:23:28.485479+00
3c92b56f-faaf-49ee-baa2-bae76e647561	7f13f993-eaf6-4c43-9fde-ac892ec275c5	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	2026-10-24 12:23:28.485479+00
a4802c48-03b5-4951-94e1-39a9beb162d6	7f13f993-eaf6-4c43-9fde-ac892ec275c5	cb554b25-9993-4f6f-8335-bd08c25a3cfd	2026-10-24 12:23:28.485479+00
a90ce9ee-7f47-4a2e-a3e7-410c0ae98f48	7f13f993-eaf6-4c43-9fde-ac892ec275c5	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	2026-10-24 12:23:28.485479+00
ef68d555-2610-46d5-a09d-d1d69f94856a	7f13f993-eaf6-4c43-9fde-ac892ec275c5	f38cb015-416f-48b3-b4f8-97fa0c1e530e	2026-10-24 12:23:28.485479+00
fca5f59a-2a4e-417a-aee9-75f4ca849dff	7f13f993-eaf6-4c43-9fde-ac892ec275c5	e3ae000b-f323-4c6f-838b-f5fbc1bf981c	2026-10-24 12:23:28.485479+00
19e1499c-afef-4afe-8c19-077df69e9090	7f13f993-eaf6-4c43-9fde-ac892ec275c5	c8964ac0-0154-45fa-8062-6cedded4ab6d	2026-10-24 12:23:28.485479+00
\.


--
-- Data for Name: role_data_scopes; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.role_data_scopes (id, tenant_id, role_id, permission_id, scope_type, organization_ids, created_at) FROM stdin;
27a33583-4961-46d4-aba7-ecdc4d8e3650	fe4a8854-cc40-451d-842a-930a3c816356	3cf6d506-9ce1-41cc-950c-5623e4c896d1	4ca738d3-6966-4f08-8324-16c4480bdd88	self	[]	2026-10-23 16:53:14.473478+00
6967fe2c-b09d-467a-a90d-b6a080fb0bd3	9c87c06c-6adf-4335-b06b-362512ec62c2	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	e9269041-5acd-45d2-80bc-f809ca90c516	self	[]	2026-10-24 07:21:51.482006+00
494e49e1-628e-4968-b79f-dad84895c85b	9c87c06c-6adf-4335-b06b-362512ec62c2	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	52eacaae-aa6d-4fdf-a33d-7b94976ca821	self	[]	2026-10-24 07:21:51.482006+00
a932d2a4-1886-43ff-82e0-9e53e4b88f50	9c87c06c-6adf-4335-b06b-362512ec62c2	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	9d9fa83e-c39e-4f58-8302-5ebc343b82c7	self	[]	2026-10-24 07:21:51.482006+00
e341814b-9cf3-46db-8887-2d0bc93d9fdc	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	1955ea73-e035-431d-a86a-be9e5c4600ea	self	[]	2026-10-24 07:37:36.633237+00
174c718b-896b-49f6-be8c-f9c958c3961f	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	099af76d-fe81-4736-b200-898b53e65b88	self	[]	2026-10-24 07:37:36.633237+00
bb32741c-f263-4754-b43b-88f619e208c9	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	e94346df-56ae-494d-8ce8-af9be7d3f5a8	self	[]	2026-10-24 07:37:36.633237+00
dac87868-fefc-42a7-8eac-a99f76326ac4	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	7872c65d-0ff3-4a15-95ce-39789a19ab86	self	[]	2026-10-24 07:37:36.633237+00
b65e6846-5c64-46fd-9f69-b9bae3e894e8	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	d6271b0f-729d-49f3-b4f1-9146ea684850	self	[]	2026-10-24 07:37:36.633237+00
72b9b468-ca94-4311-8a89-3c4e474adf59	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	e81dfc88-8edb-4352-87b1-751beda5f0c6	self	[]	2026-10-24 07:37:36.633237+00
d7dcc720-64a2-4dd2-aaea-66527a31fbac	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	b58b3152-f96c-427c-8754-acb9d85bff69	self	[]	2026-10-24 07:37:36.633237+00
cea047d2-5bb2-440d-a907-8fa1f75a8bae	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	9872643d-6d9c-489b-9339-b87db8e59659	self	[]	2026-10-24 07:37:36.633237+00
e4460878-c456-46fa-9833-d6787830e77f	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	5ea79933-3369-4020-991f-a50809571caa	self	[]	2026-10-24 07:37:36.633237+00
e0293ce9-a88e-47b1-9366-2125bf2238b4	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	f10f0c43-6d8b-4b53-9271-88255609f007	self	[]	2026-10-24 07:37:36.633237+00
0338b165-46e2-40fd-8d1c-9a3fc8933ee4	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	d2bcf175-8d20-450b-a5cf-2bb73053ad11	self	[]	2026-10-24 07:37:36.633237+00
4d884e9c-4547-4915-bea2-e395cac2ca0b	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	6494dac0-c095-4397-859e-06bdf3b9207d	self	[]	2026-10-24 07:37:36.633237+00
7b5b1e8c-ee5f-48c6-a0d3-0e06b7671725	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	6e653603-2458-4ee7-8ace-566c56dc1719	self	[]	2026-10-24 07:37:36.633237+00
2643571d-d49c-43e2-8c51-282071767aeb	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	a86721fa-348e-4347-956d-0686799fa35b	self	[]	2026-10-24 07:37:36.633237+00
156c1a30-bd23-49d1-af8e-eb3300a10d8c	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	1f025374-040d-4f76-84d3-6bf2066dbe68	self	[]	2026-10-24 07:37:36.633237+00
46b30905-33b8-4f31-ac1f-3003bb722415	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	513c5f07-fa1c-4d87-8869-98fb4f73471a	self	[]	2026-10-24 07:37:36.633237+00
5cfdaa94-4c34-4191-a1e4-0ae9a1d1ed73	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	afb8e08f-ba6d-4605-8d15-86d6415d4997	self	[]	2026-10-24 07:37:36.633237+00
887001f7-cc8c-478d-90a5-e377dda71a0e	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	846cd794-54a6-4226-9b1f-459beb154d95	self	[]	2026-10-24 07:37:36.633237+00
5d619e04-7e48-4ea0-8081-c99e6fbbf376	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	74278a34-2fac-466c-b928-28b18e797f9b	self	[]	2026-10-24 07:37:36.633237+00
5c2193d4-e45b-4105-81f9-6c4f38579505	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	24844308-f3d9-4e4c-a830-ad4621a03c16	self	[]	2026-10-24 07:37:36.633237+00
aec3c486-b177-47e0-9c1a-9c90f45f7461	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	1dc4588e-36ee-4040-af55-b31fb5c82cef	self	[]	2026-10-24 07:37:36.633237+00
ab142f49-3a85-49a7-a736-679a90efab54	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	910a290c-fad1-478e-bf40-84e1f1eef0ba	self	[]	2026-10-24 07:37:36.633237+00
012e8a3f-8cc7-4e9d-8dcc-52a910a436a7	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	c333f013-4acd-47a6-a8e5-e3ca459096c5	self	[]	2026-10-24 07:37:36.633237+00
ffad9f97-75d1-4c89-afa4-8e0c9af96d2c	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	eb9b2aaa-b7e1-42e3-9204-3e3361f00f45	self	[]	2026-10-24 07:37:36.633237+00
cb167b83-33f6-4045-a7ec-d123980ed29b	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	8a908a46-32e9-43a4-a5b0-8cdd169a5fbf	self	[]	2026-10-24 07:37:36.633237+00
32ad7db2-1286-4a72-83ca-3b6bcf4f2951	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	ec6d9b31-c3d8-4ff8-a1a5-caed44ba37ed	self	[]	2026-10-24 07:37:36.633237+00
d53a8a37-b325-4056-b714-ba597b0b0500	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	1eeb66f2-3ed8-46be-a555-43d8590c1d16	self	[]	2026-10-24 07:37:36.633237+00
46d74c33-7997-4dab-8fef-9132a8c0fc87	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	508712af-94e0-4e20-981c-a8b50fd29d8f	self	[]	2026-10-24 07:37:36.633237+00
d5ee3ac3-32be-4a01-a9bd-3816add41889	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	f72afa56-d671-472d-bb1d-d78848075e84	self	[]	2026-10-24 07:37:36.633237+00
87c0804a-5ae3-4dd0-9ab9-aa6ab512100e	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	71977a98-9fc8-4957-ab52-c8bab20f80b8	self	[]	2026-10-24 07:37:36.633237+00
5618c860-0f61-45bb-a553-31588f96745f	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	dfbd60b6-4b24-4d03-a09b-ce210b354c7e	self	[]	2026-10-24 07:37:36.633237+00
a6197a50-14b6-4469-9eec-fafa9952eed7	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	5a07b0cd-2329-4460-806c-deaf15fc447a	self	[]	2026-10-24 07:37:36.633237+00
d47ad8e5-9272-4dee-a30d-2558d6d80077	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	98d380a0-0ad0-4cb7-b335-e09911444bca	self	[]	2026-10-24 07:37:36.633237+00
1553143c-4cec-40f5-aa5b-3ffa150e0814	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	aa4d3f5a-cf9b-4004-8636-bd9d68cd0268	self	[]	2026-10-24 07:37:36.633237+00
c4e7df0f-499a-495a-8bd8-a0aa8ad70ee9	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	6c69bfb4-6849-404f-9087-e7edd64bfcd1	self	[]	2026-10-24 07:37:36.633237+00
8720ad07-f130-4194-ad67-4f14f31a389a	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	61c030cb-a174-4a05-8024-a0efc76bbb3d	self	[]	2026-10-24 07:37:36.633237+00
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.role_permissions (id, role_id, permission_id, resource_id) FROM stdin;
faf59caf-d4a5-4c2f-be4b-138dce138a9e	7fbd7166-1f58-44f6-bf3e-102ad7687666	5a276f10-f641-44c3-911e-49eeb30b5268	\N
fffcdf65-09a6-4e37-9d52-7aff85ecf9c2	7fbd7166-1f58-44f6-bf3e-102ad7687666	f22381dd-18c4-4cc6-8898-227c0800cef8	\N
d08696bc-a0fa-44e9-9fd2-1e1402e7f08d	7fbd7166-1f58-44f6-bf3e-102ad7687666	7908d053-973d-4bb3-9d3d-729b90e7b809	\N
ee101044-4be8-485d-ba0f-af12bebbaf0d	7fbd7166-1f58-44f6-bf3e-102ad7687666	867e0b7e-f8c0-4fab-a715-8e2b42019b6d	\N
14ab9290-343d-4e59-b6fb-c0835e358ef6	7fbd7166-1f58-44f6-bf3e-102ad7687666	f774f5e5-1cf7-47c1-b36e-6fddfe24ceda	\N
d40c5205-709e-4695-9a01-17a5f1ac08dd	7fbd7166-1f58-44f6-bf3e-102ad7687666	0b9f5e4c-cc9c-472c-a614-5a6aff52a58f	\N
4602299c-c56d-4f34-9435-47e16763a502	7fbd7166-1f58-44f6-bf3e-102ad7687666	cb32309e-8275-4e1a-b28e-7f60ec0a5db1	\N
5e91efc6-3f70-4002-94f8-fd4b496f313e	7fbd7166-1f58-44f6-bf3e-102ad7687666	de2e81d4-5eb3-48dd-b2ae-7cc034fe0bc1	\N
5e6e5750-472c-4645-abe9-fd7f11b84d3f	7fbd7166-1f58-44f6-bf3e-102ad7687666	8f1037de-e1b0-4236-bf69-5fb41be396db	\N
dfd1f1d8-d90e-4c9c-9d07-aa8d311e52b6	7fbd7166-1f58-44f6-bf3e-102ad7687666	9329a1d8-14cc-4f3d-9c89-eeeb2bd7643d	\N
e1c93e72-e594-433b-8c24-1870c495445c	7fbd7166-1f58-44f6-bf3e-102ad7687666	a204f626-77e6-4e9d-a476-d211b44ce3ab	\N
e811f141-d0be-4ace-8751-168ad52b71ec	7fbd7166-1f58-44f6-bf3e-102ad7687666	45be6501-9f6b-4bbb-920d-3fc5107a484e	\N
b4d9bbae-96a7-48f3-a996-625d42d8cfb8	7fbd7166-1f58-44f6-bf3e-102ad7687666	88ac0048-c292-4c11-8e08-bd52044394e6	\N
d968ce72-15a5-4a05-b1d2-6c156ea54e07	7fbd7166-1f58-44f6-bf3e-102ad7687666	85135f6c-cb27-4f84-b483-6103f2be48db	\N
0769d05b-2bc9-4586-8376-6767b24546ce	7fbd7166-1f58-44f6-bf3e-102ad7687666	493d71f1-5d0b-4816-b8be-a5bb244b8bf5	\N
f494dd30-dd33-4542-a0fd-f97c75acf1ca	7fbd7166-1f58-44f6-bf3e-102ad7687666	d95fe6d0-ff21-4382-95f1-20004cc55d5f	\N
a9029478-54f5-4c9b-8fed-300655f31b04	7fbd7166-1f58-44f6-bf3e-102ad7687666	de89e761-490c-429f-928f-c405adaeadf8	\N
387e63d2-f74a-40ba-a2b0-68a4a7b1f9ff	7fbd7166-1f58-44f6-bf3e-102ad7687666	731c7a90-1ffe-462c-9824-7a3f73528fdc	\N
ccfeca9d-ff8c-4679-bf38-ac97c41a6b16	7fbd7166-1f58-44f6-bf3e-102ad7687666	ecf0b8f1-ee8f-4c17-a3e2-df53f8a8576c	\N
159047be-160f-4088-9226-01aa2a431a2a	7fbd7166-1f58-44f6-bf3e-102ad7687666	d9ec0b31-e44b-459d-9a1a-22e5d545e763	\N
7c8d5e9c-c2a9-4459-852e-797bdbdeb233	7fbd7166-1f58-44f6-bf3e-102ad7687666	f184b71f-9440-4508-9829-18eb2a8ae6dc	\N
1c7a1263-af90-4f4f-b0db-d5e7c27cb40a	7fbd7166-1f58-44f6-bf3e-102ad7687666	56579e69-cb65-4324-aecc-0e94defdeea3	\N
6e0c09e4-3009-4c71-ac9d-d6017fad0fd9	7fbd7166-1f58-44f6-bf3e-102ad7687666	ddaa8759-29fc-4a1b-bde7-955c533254d9	\N
f6557583-56f8-4333-9850-3170ba0ef1e2	7fbd7166-1f58-44f6-bf3e-102ad7687666	76751cb5-4ed9-473e-ae9e-e92479d8d883	\N
31a9a782-5376-4035-a154-8eaf68197fe4	7fbd7166-1f58-44f6-bf3e-102ad7687666	2dbfc849-9767-4e6e-90e2-7f014cb9e905	\N
cfedd359-c978-4546-bc83-d95d05a1718a	7fbd7166-1f58-44f6-bf3e-102ad7687666	df400307-7f14-45da-899c-67320517caa7	\N
ac2c8cd6-5dcc-450a-bfd9-fb98cc071949	7fbd7166-1f58-44f6-bf3e-102ad7687666	b273a84a-33fa-44c5-b291-90d732815829	\N
d229e877-506f-4312-bc17-4d855aeab7d5	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	0b9f5e4c-cc9c-472c-a614-5a6aff52a58f	\N
2e415962-7572-4280-a53f-f11f386b3c21	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	de2e81d4-5eb3-48dd-b2ae-7cc034fe0bc1	\N
95394f7a-e441-4053-ac3c-879c9ecf7d7d	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	9329a1d8-14cc-4f3d-9c89-eeeb2bd7643d	\N
52bf5657-a0af-498d-ad30-019cb7ab0664	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	a204f626-77e6-4e9d-a476-d211b44ce3ab	\N
70ae00da-1380-4bee-bb24-ae3edb147661	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	45be6501-9f6b-4bbb-920d-3fc5107a484e	\N
62ff2a21-08e8-477b-ab41-a8079ae21c3c	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	88ac0048-c292-4c11-8e08-bd52044394e6	\N
75cdb5f0-3d39-4329-b54a-791304d2717b	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	85135f6c-cb27-4f84-b483-6103f2be48db	\N
37ccf0e5-1677-4ec4-a2d0-4398f6effafe	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	493d71f1-5d0b-4816-b8be-a5bb244b8bf5	\N
4b2a3d9b-8b64-4214-b6f9-d644768c1a58	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	ecf0b8f1-ee8f-4c17-a3e2-df53f8a8576c	\N
cf5ff70c-ebeb-4acd-aebb-29e2d669d223	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	f184b71f-9440-4508-9829-18eb2a8ae6dc	\N
b3553914-1394-4910-a594-182caec5bf95	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	56579e69-cb65-4324-aecc-0e94defdeea3	\N
09255fa4-8f4e-4bc4-8937-a5de05838711	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	76751cb5-4ed9-473e-ae9e-e92479d8d883	\N
aed2a56a-cddb-4e24-91b1-fc56a74016b3	6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	2dbfc849-9767-4e6e-90e2-7f014cb9e905	\N
43ed978e-4f86-4ac5-897d-ac4d8f650060	f4a857ce-150c-4163-a628-0d844d30d788	0b9f5e4c-cc9c-472c-a614-5a6aff52a58f	\N
e38d3010-070c-411c-a302-f5cee2f29be3	f4a857ce-150c-4163-a628-0d844d30d788	de2e81d4-5eb3-48dd-b2ae-7cc034fe0bc1	\N
46938f0c-bddd-45d0-8e7d-fdd25a5c9a58	f4a857ce-150c-4163-a628-0d844d30d788	9329a1d8-14cc-4f3d-9c89-eeeb2bd7643d	\N
09dfb5ce-7062-46b5-860b-c3b897413883	f4a857ce-150c-4163-a628-0d844d30d788	a204f626-77e6-4e9d-a476-d211b44ce3ab	\N
1444c658-876f-4654-803c-162d44416b82	f4a857ce-150c-4163-a628-0d844d30d788	45be6501-9f6b-4bbb-920d-3fc5107a484e	\N
cf068c1a-73d6-4682-a210-cb0022e51ac9	f4a857ce-150c-4163-a628-0d844d30d788	88ac0048-c292-4c11-8e08-bd52044394e6	\N
5d8d3c36-cfea-449d-a44b-d8a34d753471	f4a857ce-150c-4163-a628-0d844d30d788	85135f6c-cb27-4f84-b483-6103f2be48db	\N
531d717d-e6a2-4729-82f0-9fd25a0710f4	f4a857ce-150c-4163-a628-0d844d30d788	493d71f1-5d0b-4816-b8be-a5bb244b8bf5	\N
3730b114-50ff-4129-a72b-ecebd4bb81c2	f4a857ce-150c-4163-a628-0d844d30d788	ecf0b8f1-ee8f-4c17-a3e2-df53f8a8576c	\N
2092557e-6516-4a49-819c-70f061001caf	f4a857ce-150c-4163-a628-0d844d30d788	f184b71f-9440-4508-9829-18eb2a8ae6dc	\N
2d5fe671-2f12-4ef9-b3e2-9cab600a24fb	f4a857ce-150c-4163-a628-0d844d30d788	56579e69-cb65-4324-aecc-0e94defdeea3	\N
a20a795b-9b06-415d-afdd-42fc72277ce8	f4a857ce-150c-4163-a628-0d844d30d788	76751cb5-4ed9-473e-ae9e-e92479d8d883	\N
5c9f7344-0317-4d47-aa6b-b31a82c2c512	f4a857ce-150c-4163-a628-0d844d30d788	2dbfc849-9767-4e6e-90e2-7f014cb9e905	\N
38452f09-6979-4c85-b831-a8ed93aaf954	96aceeb3-6270-4a8d-ac35-f80e90363142	0b9f5e4c-cc9c-472c-a614-5a6aff52a58f	\N
3cd2c395-045e-4139-a006-15897a383338	96aceeb3-6270-4a8d-ac35-f80e90363142	9329a1d8-14cc-4f3d-9c89-eeeb2bd7643d	\N
fa1fa7dd-67c2-4977-b517-c0001e94f365	96aceeb3-6270-4a8d-ac35-f80e90363142	a204f626-77e6-4e9d-a476-d211b44ce3ab	\N
9e50b3cf-4e20-488e-b493-fe30f54ee7e1	96aceeb3-6270-4a8d-ac35-f80e90363142	45be6501-9f6b-4bbb-920d-3fc5107a484e	\N
ea6b14af-1ddb-46fe-bcb8-32898a5c8eea	96aceeb3-6270-4a8d-ac35-f80e90363142	88ac0048-c292-4c11-8e08-bd52044394e6	\N
edf16ed3-00da-4d72-9ef0-4a4a851e4071	96aceeb3-6270-4a8d-ac35-f80e90363142	85135f6c-cb27-4f84-b483-6103f2be48db	\N
15252cf0-32b0-4723-98cf-2f9e5b3dcebe	96aceeb3-6270-4a8d-ac35-f80e90363142	493d71f1-5d0b-4816-b8be-a5bb244b8bf5	\N
cfa63858-aa6d-47f5-8bc5-49e34d86e751	96aceeb3-6270-4a8d-ac35-f80e90363142	d95fe6d0-ff21-4382-95f1-20004cc55d5f	\N
482b0aa8-d2dd-45a3-9b9b-fa1266bddf2e	96aceeb3-6270-4a8d-ac35-f80e90363142	de89e761-490c-429f-928f-c405adaeadf8	\N
b5f62291-452d-4a5d-b4bf-bf73e5f182c7	96aceeb3-6270-4a8d-ac35-f80e90363142	731c7a90-1ffe-462c-9824-7a3f73528fdc	\N
a3213e60-8d1f-4c50-8dde-9bbde95ffe2c	96aceeb3-6270-4a8d-ac35-f80e90363142	ecf0b8f1-ee8f-4c17-a3e2-df53f8a8576c	\N
da12d3e3-eef7-4982-b787-9623dde84edd	96aceeb3-6270-4a8d-ac35-f80e90363142	d9ec0b31-e44b-459d-9a1a-22e5d545e763	\N
c55c0d1c-04eb-438c-befd-91b79d5987e2	96aceeb3-6270-4a8d-ac35-f80e90363142	56579e69-cb65-4324-aecc-0e94defdeea3	\N
f6cc1d0a-22cf-4d5c-a42c-ece96ff8cf30	96aceeb3-6270-4a8d-ac35-f80e90363142	ddaa8759-29fc-4a1b-bde7-955c533254d9	\N
d93e6ee5-d9ad-451c-a7e4-c4f1d66e1831	96aceeb3-6270-4a8d-ac35-f80e90363142	76751cb5-4ed9-473e-ae9e-e92479d8d883	\N
452165bf-5878-43f5-b93e-ffcf2acce7e0	96aceeb3-6270-4a8d-ac35-f80e90363142	2dbfc849-9767-4e6e-90e2-7f014cb9e905	\N
3a26cb94-f91e-427d-aeaa-763f17ce2cda	96aceeb3-6270-4a8d-ac35-f80e90363142	b273a84a-33fa-44c5-b291-90d732815829	\N
450a4fe6-627d-44b1-b04a-b80debeaadb1	3cf6d506-9ce1-41cc-950c-5623e4c896d1	4ca738d3-6966-4f08-8324-16c4480bdd88	\N
5f7e33a6-13a5-4e59-82c0-c1e96111b813	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	0b9f5e4c-cc9c-472c-a614-5a6aff52a58f	\N
82a53d3a-e9df-4375-b398-0fa0acca906c	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	9329a1d8-14cc-4f3d-9c89-eeeb2bd7643d	\N
c8214579-aba6-4cf9-ab09-f1f0c58bab12	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	a204f626-77e6-4e9d-a476-d211b44ce3ab	\N
1fac7aa0-058f-4a42-9112-4845a1f4bad9	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	45be6501-9f6b-4bbb-920d-3fc5107a484e	\N
171c8a84-28b1-4461-b111-60841be1fd17	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	88ac0048-c292-4c11-8e08-bd52044394e6	\N
f6dd62aa-65bb-4189-9d15-f9d7a0713ecd	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	85135f6c-cb27-4f84-b483-6103f2be48db	\N
4ed8d997-4aab-40ae-a4a9-9d79e512bb38	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	493d71f1-5d0b-4816-b8be-a5bb244b8bf5	\N
eb927ddb-ccb4-4767-9d5a-e43f900b1225	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	d95fe6d0-ff21-4382-95f1-20004cc55d5f	\N
28c4317e-9224-4171-9a97-7564eac92fb1	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	de89e761-490c-429f-928f-c405adaeadf8	\N
8f5ee5bb-703f-4bb2-a410-c781a0cc9c15	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	731c7a90-1ffe-462c-9824-7a3f73528fdc	\N
f273727a-580f-40ab-a038-6b4b512fa4b4	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	ecf0b8f1-ee8f-4c17-a3e2-df53f8a8576c	\N
2038e813-a473-49f8-8ece-fba3fa2e0748	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	d9ec0b31-e44b-459d-9a1a-22e5d545e763	\N
e6edf917-7165-4e6a-b5ea-fd423bfc4616	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	56579e69-cb65-4324-aecc-0e94defdeea3	\N
c80046c7-79d1-408c-9960-29a51852ca81	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	ddaa8759-29fc-4a1b-bde7-955c533254d9	\N
c8d9a97c-c788-4203-b7fd-2eef77c7a1f5	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	76751cb5-4ed9-473e-ae9e-e92479d8d883	\N
49f51d50-efc9-42e3-bb65-247a8df03041	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	2dbfc849-9767-4e6e-90e2-7f014cb9e905	\N
d34b15c0-2274-4157-bccd-1f6e3c1c20ad	8d56246c-98e7-4185-8cfc-0e8c52e15d5c	b273a84a-33fa-44c5-b291-90d732815829	\N
5264aaaf-7bc4-49d0-a909-2bcce2535049	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	e9269041-5acd-45d2-80bc-f809ca90c516	\N
aa629474-8c8f-4b6a-a93c-62810b65a23a	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	52eacaae-aa6d-4fdf-a33d-7b94976ca821	\N
556b07b6-0658-4ace-b210-324fe4377179	c287b677-9d9e-4c4a-8cb0-cd82d2d27671	9d9fa83e-c39e-4f58-8302-5ebc343b82c7	\N
4a5909fd-a003-481d-9cf1-9b97806e7087	f38cb015-416f-48b3-b4f8-97fa0c1e530e	0b9f5e4c-cc9c-472c-a614-5a6aff52a58f	\N
6dd6cc33-73a9-43c9-9191-b0bea236d9bd	f38cb015-416f-48b3-b4f8-97fa0c1e530e	9329a1d8-14cc-4f3d-9c89-eeeb2bd7643d	\N
3a1ac21b-5bee-484e-a821-fc6351dba476	f38cb015-416f-48b3-b4f8-97fa0c1e530e	a204f626-77e6-4e9d-a476-d211b44ce3ab	\N
f5d7620a-8b2b-464f-9b3b-ee9e8db9a790	f38cb015-416f-48b3-b4f8-97fa0c1e530e	45be6501-9f6b-4bbb-920d-3fc5107a484e	\N
1d05ebf5-b08e-4853-9831-35e521bfbda0	f38cb015-416f-48b3-b4f8-97fa0c1e530e	88ac0048-c292-4c11-8e08-bd52044394e6	\N
f8193f01-f788-497f-98fd-886a43e46392	f38cb015-416f-48b3-b4f8-97fa0c1e530e	85135f6c-cb27-4f84-b483-6103f2be48db	\N
024472d9-240d-4868-aef7-124ff214a2d4	f38cb015-416f-48b3-b4f8-97fa0c1e530e	493d71f1-5d0b-4816-b8be-a5bb244b8bf5	\N
785eee1d-6240-41d4-b259-a3baca64383a	f38cb015-416f-48b3-b4f8-97fa0c1e530e	d95fe6d0-ff21-4382-95f1-20004cc55d5f	\N
7f54fad4-6de1-40eb-adcc-cd06e33bbd8c	f38cb015-416f-48b3-b4f8-97fa0c1e530e	de89e761-490c-429f-928f-c405adaeadf8	\N
203174a6-4555-410d-9d3c-dec7c3318923	f38cb015-416f-48b3-b4f8-97fa0c1e530e	731c7a90-1ffe-462c-9824-7a3f73528fdc	\N
e9b9c056-dba9-4328-b6b3-eb3cc06cd2bd	f38cb015-416f-48b3-b4f8-97fa0c1e530e	ecf0b8f1-ee8f-4c17-a3e2-df53f8a8576c	\N
0eab3d37-c3c2-45c9-b9e6-4342657ddd6f	f38cb015-416f-48b3-b4f8-97fa0c1e530e	d9ec0b31-e44b-459d-9a1a-22e5d545e763	\N
d8056c52-63a8-49c4-8dc5-04b051bd0bc2	f38cb015-416f-48b3-b4f8-97fa0c1e530e	56579e69-cb65-4324-aecc-0e94defdeea3	\N
f080b50a-35a2-4988-ab0d-c8cca949ba6c	f38cb015-416f-48b3-b4f8-97fa0c1e530e	ddaa8759-29fc-4a1b-bde7-955c533254d9	\N
20e94354-98de-41b6-8611-aa10fadd759d	f38cb015-416f-48b3-b4f8-97fa0c1e530e	76751cb5-4ed9-473e-ae9e-e92479d8d883	\N
fa7394d0-1f5a-47f2-927e-2eb5a9ee99b7	f38cb015-416f-48b3-b4f8-97fa0c1e530e	2dbfc849-9767-4e6e-90e2-7f014cb9e905	\N
04cb80ab-e405-4776-993a-46723194587e	f38cb015-416f-48b3-b4f8-97fa0c1e530e	b273a84a-33fa-44c5-b291-90d732815829	\N
588d68c9-d4bf-4239-8ced-bcd730840b2d	c8964ac0-0154-45fa-8062-6cedded4ab6d	099af76d-fe81-4736-b200-898b53e65b88	\N
d1db4817-172d-4dd5-9174-e4c40f9627c6	c8964ac0-0154-45fa-8062-6cedded4ab6d	e81dfc88-8edb-4352-87b1-751beda5f0c6	\N
09620631-707b-4ee2-a035-6cb55db8284c	c8964ac0-0154-45fa-8062-6cedded4ab6d	f10f0c43-6d8b-4b53-9271-88255609f007	\N
7087e71f-4a00-4cfa-a4e0-2b2e157d7d0e	c8964ac0-0154-45fa-8062-6cedded4ab6d	a86721fa-348e-4347-956d-0686799fa35b	\N
27ed131e-4763-4aa7-bf74-e870c361c6f9	c8964ac0-0154-45fa-8062-6cedded4ab6d	846cd794-54a6-4226-9b1f-459beb154d95	\N
da56a461-c8dd-4327-b14c-9f5d1c6dab54	c8964ac0-0154-45fa-8062-6cedded4ab6d	910a290c-fad1-478e-bf40-84e1f1eef0ba	\N
629dc12b-f7e1-4c98-ba89-0b6f0abc24c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	ec6d9b31-c3d8-4ff8-a1a5-caed44ba37ed	\N
1c74afdd-e8d9-40ce-8aa0-12f38451bf2a	c8964ac0-0154-45fa-8062-6cedded4ab6d	71977a98-9fc8-4957-ab52-c8bab20f80b8	\N
5e36b15a-a651-4ab0-9147-dafedc94a84b	c8964ac0-0154-45fa-8062-6cedded4ab6d	aa4d3f5a-cf9b-4004-8636-bd9d68cd0268	\N
d8e4fe6d-f103-400f-9b0b-81b9f896f4b6	c8964ac0-0154-45fa-8062-6cedded4ab6d	1955ea73-e035-431d-a86a-be9e5c4600ea	\N
52247fd5-9100-4982-82e1-510023dfc78d	c8964ac0-0154-45fa-8062-6cedded4ab6d	d6271b0f-729d-49f3-b4f1-9146ea684850	\N
a96a2799-9b17-4db4-b4b9-7896b4c29669	c8964ac0-0154-45fa-8062-6cedded4ab6d	5ea79933-3369-4020-991f-a50809571caa	\N
054cd90b-acbe-4f2b-b261-459673e24cec	c8964ac0-0154-45fa-8062-6cedded4ab6d	6e653603-2458-4ee7-8ace-566c56dc1719	\N
c9db9758-9bc0-42da-b974-785d8267c10c	c8964ac0-0154-45fa-8062-6cedded4ab6d	afb8e08f-ba6d-4605-8d15-86d6415d4997	\N
27630d8f-f7e3-45f3-8516-3c5c8c8141cd	c8964ac0-0154-45fa-8062-6cedded4ab6d	1dc4588e-36ee-4040-af55-b31fb5c82cef	\N
a3250f42-dfa3-4ebe-8ce2-c8f1c740e55c	c8964ac0-0154-45fa-8062-6cedded4ab6d	8a908a46-32e9-43a4-a5b0-8cdd169a5fbf	\N
ee227072-c206-4dec-92d0-d9da9b32fddb	c8964ac0-0154-45fa-8062-6cedded4ab6d	f72afa56-d671-472d-bb1d-d78848075e84	\N
6b58c504-54d7-46b1-9bf3-f00856623bd1	c8964ac0-0154-45fa-8062-6cedded4ab6d	98d380a0-0ad0-4cb7-b335-e09911444bca	\N
9cb7ecfd-27fd-4e7f-969c-4131213f4e41	c8964ac0-0154-45fa-8062-6cedded4ab6d	e94346df-56ae-494d-8ce8-af9be7d3f5a8	\N
748b89c7-4a67-4e5c-8301-3dee98aaa2a7	c8964ac0-0154-45fa-8062-6cedded4ab6d	b58b3152-f96c-427c-8754-acb9d85bff69	\N
549a4bfb-2a1f-45d8-adbd-4fa231c50764	c8964ac0-0154-45fa-8062-6cedded4ab6d	d2bcf175-8d20-450b-a5cf-2bb73053ad11	\N
2adfa744-f2c9-4d41-9313-78d0ba4fab0d	c8964ac0-0154-45fa-8062-6cedded4ab6d	1f025374-040d-4f76-84d3-6bf2066dbe68	\N
bc9d0eea-f8c6-4c2e-ace4-16453bf2ea58	c8964ac0-0154-45fa-8062-6cedded4ab6d	74278a34-2fac-466c-b928-28b18e797f9b	\N
790b5f52-fc4f-4fe3-9f5b-20a04f1d337e	c8964ac0-0154-45fa-8062-6cedded4ab6d	c333f013-4acd-47a6-a8e5-e3ca459096c5	\N
7f39ea12-dba6-43ca-8ca8-df628f57f042	c8964ac0-0154-45fa-8062-6cedded4ab6d	1eeb66f2-3ed8-46be-a555-43d8590c1d16	\N
8bca51b0-7c47-4304-81a8-8f1978b952c7	c8964ac0-0154-45fa-8062-6cedded4ab6d	dfbd60b6-4b24-4d03-a09b-ce210b354c7e	\N
f1638dc3-363b-4400-aed9-6e04a805d21a	c8964ac0-0154-45fa-8062-6cedded4ab6d	6c69bfb4-6849-404f-9087-e7edd64bfcd1	\N
8b663e66-8eb2-4da0-b6d7-e04159a2ce11	c8964ac0-0154-45fa-8062-6cedded4ab6d	7872c65d-0ff3-4a15-95ce-39789a19ab86	\N
4a8184e3-3d4e-4e6c-8441-1f10a921175a	c8964ac0-0154-45fa-8062-6cedded4ab6d	9872643d-6d9c-489b-9339-b87db8e59659	\N
eb5444bd-a28d-4f3c-b183-17442e400664	c8964ac0-0154-45fa-8062-6cedded4ab6d	6494dac0-c095-4397-859e-06bdf3b9207d	\N
310d7f62-2f51-4b93-89d2-e2ff0a5fce94	c8964ac0-0154-45fa-8062-6cedded4ab6d	513c5f07-fa1c-4d87-8869-98fb4f73471a	\N
c861444b-db6d-41b1-87fd-215276a644be	c8964ac0-0154-45fa-8062-6cedded4ab6d	24844308-f3d9-4e4c-a830-ad4621a03c16	\N
9ef8abd1-c345-43fe-bb0a-c25e1db7234c	c8964ac0-0154-45fa-8062-6cedded4ab6d	eb9b2aaa-b7e1-42e3-9204-3e3361f00f45	\N
79919f50-6b57-4163-91f3-fd6c58643239	c8964ac0-0154-45fa-8062-6cedded4ab6d	508712af-94e0-4e20-981c-a8b50fd29d8f	\N
f8d4616b-0cf9-4c0b-9c09-6c782c87f7a2	c8964ac0-0154-45fa-8062-6cedded4ab6d	5a07b0cd-2329-4460-806c-deaf15fc447a	\N
054374e5-21d0-45f6-ad29-c8281126c789	c8964ac0-0154-45fa-8062-6cedded4ab6d	61c030cb-a174-4a05-8024-a0efc76bbb3d	\N
26ca0cd8-3596-458d-ab67-94565904d26c	5864ee13-77ba-48a7-b721-011d0b9eb35c	9329a1d8-14cc-4f3d-9c89-eeeb2bd7643d	\N
d50c241c-83ca-4787-b081-4da2a93c0268	5864ee13-77ba-48a7-b721-011d0b9eb35c	a204f626-77e6-4e9d-a476-d211b44ce3ab	\N
d134d351-fd76-4847-9a54-202810ca20cb	5864ee13-77ba-48a7-b721-011d0b9eb35c	45be6501-9f6b-4bbb-920d-3fc5107a484e	\N
8b942fac-bf86-49b2-8973-878efcb848db	5864ee13-77ba-48a7-b721-011d0b9eb35c	88ac0048-c292-4c11-8e08-bd52044394e6	\N
095f0198-5c2b-447f-9bbc-3c04e6b09626	5864ee13-77ba-48a7-b721-011d0b9eb35c	85135f6c-cb27-4f84-b483-6103f2be48db	\N
5c77c718-9601-4c81-bfa8-526dcba41a5b	5864ee13-77ba-48a7-b721-011d0b9eb35c	493d71f1-5d0b-4816-b8be-a5bb244b8bf5	\N
3d8e96eb-e603-43fe-8ee9-836d7e79516f	5864ee13-77ba-48a7-b721-011d0b9eb35c	d95fe6d0-ff21-4382-95f1-20004cc55d5f	\N
e4fd9197-cd52-4638-848c-40c9cc05b22f	5864ee13-77ba-48a7-b721-011d0b9eb35c	f184b71f-9440-4508-9829-18eb2a8ae6dc	\N
3bb3002a-14e0-463a-8178-e2d7722e926f	5864ee13-77ba-48a7-b721-011d0b9eb35c	56579e69-cb65-4324-aecc-0e94defdeea3	\N
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.roles (id, tenant_id, application_id, kind, key, name, description, status, created_at) FROM stdin;
7fbd7166-1f58-44f6-bf3e-102ad7687666	9c87c06c-6adf-4335-b06b-362512ec62c2	\N	platform	platform.super_admin	平台超级管理员	L1：全部 iam.* 管理面码；可代管任意租户/应用；默认无业务码	active	2026-10-23 16:26:39.234987+00
6eb2c3e8-2291-4fe2-ac4f-9600ea9589ac	9c87c06c-6adf-4335-b06b-362512ec62c2	\N	tenant	tenant.org_admin	租户管理员	L3：组织、成员、用户组、邀请与只读目录/模拟/模型；可任命应用管理员（iam.app_role.assign），无应用管理/主题/审计	active	2026-10-23 16:26:39.234987+00
f4a857ce-150c-4163-a628-0d844d30d788	fe4a8854-cc40-451d-842a-930a3c816356	\N	tenant	tenant.org_admin	租户管理员	L3：组织、成员、用户组、邀请与只读目录/模拟/模型；可任命应用管理员（iam.app_role.assign），无应用管理/主题/审计	active	2026-10-23 16:26:39.234987+00
96aceeb3-6270-4a8d-ac35-f80e90363142	fe4a8854-cc40-451d-842a-930a3c816356	a680e9d6-654f-492a-85b1-ef428bd97976	application	app.admin	应用管理员	L2：本应用配置/接入/密钥与应用角色成员管理 + 所属租户人治码（成员/邀请/组/组织/审计）与只读目录/模拟/模型/主题	active	2026-10-23 16:53:14.473478+00
3cf6d506-9ce1-41cc-950c-5623e4c896d1	fe4a8854-cc40-451d-842a-930a3c816356	a680e9d6-654f-492a-85b1-ef428bd97976	application	app.member	应用成员	L4：无管理面码；可被授予业务权限与数据范围	active	2026-10-23 16:53:14.473478+00
8d56246c-98e7-4185-8cfc-0e8c52e15d5c	9c87c06c-6adf-4335-b06b-362512ec62c2	27bf3137-7910-4544-9e62-9789d97aab0c	application	app.admin	应用管理员	L2：本应用配置/接入/密钥与应用角色成员管理 + 所属租户人治码（成员/邀请/组/组织/审计）与只读目录/模拟/模型/主题	active	2026-10-24 07:20:26.896679+00
cb554b25-9993-4f6f-8335-bd08c25a3cfd	9c87c06c-6adf-4335-b06b-362512ec62c2	27bf3137-7910-4544-9e62-9789d97aab0c	application	app.member	应用成员	L4：无管理面码；可被授予业务权限与数据范围	active	2026-10-24 07:20:26.896679+00
c287b677-9d9e-4c4a-8cb0-cd82d2d27671	9c87c06c-6adf-4335-b06b-362512ec62c2	27bf3137-7910-4544-9e62-9789d97aab0c	application	crud-demo	CRUD Demo	SDK 联调专用角色	active	2026-10-24 07:21:51.184075+00
f38cb015-416f-48b3-b4f8-97fa0c1e530e	9c87c06c-6adf-4335-b06b-362512ec62c2	5fd4169f-b222-4864-b00a-95325083ce25	application	app.admin	应用管理员	L2：本应用配置/接入/密钥与应用角色成员管理 + 所属租户人治码（成员/邀请/组/组织/审计）与只读目录/模拟/模型/主题	active	2026-10-24 07:37:33.258979+00
e3ae000b-f323-4c6f-838b-f5fbc1bf981c	9c87c06c-6adf-4335-b06b-362512ec62c2	5fd4169f-b222-4864-b00a-95325083ce25	application	app.member	应用成员	L4：无管理面码；可被授予业务权限与数据范围	active	2026-10-24 07:37:33.258979+00
c8964ac0-0154-45fa-8062-6cedded4ab6d	9c87c06c-6adf-4335-b06b-362512ec62c2	5fd4169f-b222-4864-b00a-95325083ce25	application	deerflow_member	DeerFlow 成员	Default DeerFlow business role (self data scope)	active	2026-10-24 07:37:35.002998+00
5864ee13-77ba-48a7-b721-011d0b9eb35c	7acec14b-8ca2-4b3f-a5cd-5920142db325	\N	tenant	tenant.org_admin	租户管理员	L3：组织、成员、用户组、数据范围与本租户应用只读；可通过 iam.app_role.assign 任命应用管理员	active	2026-10-27 08:24:19.943802+00
\.


--
-- Data for Name: tenant_memberships; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.tenant_memberships (id, tenant_id, user_id, status, auth_version, created_at) FROM stdin;
44bfe126-3bf3-4d17-9ebd-4e39d054171a	fe4a8854-cc40-451d-842a-930a3c816356	3d84740b-fcc5-401a-89cc-8408ccd004da	active	1	2026-10-23 16:53:14.473478+00
db238b0d-7e28-4ec0-9726-e34994a670fe	fe4a8854-cc40-451d-842a-930a3c816356	08b2ecea-9232-4479-9c47-dbcd2befc0af	active	1	2026-10-23 16:53:14.473478+00
52dc0ceb-26eb-4db3-8221-7fa416e5a7ca	fe4a8854-cc40-451d-842a-930a3c816356	427efcf4-76a2-4200-8911-807d53aec55b	active	1	2026-10-23 16:53:14.473478+00
700f02fb-aa59-4f02-babc-bd0697122770	9c87c06c-6adf-4335-b06b-362512ec62c2	0691da35-9905-4b03-a3d1-f07578e09ac8	active	1	2026-10-24 07:21:51.645196+00
a9cb2c45-b92a-4484-9597-b4a1de950f37	9c87c06c-6adf-4335-b06b-362512ec62c2	ad27a767-01c3-44be-9794-ba2e33eb2522	active	3	2026-10-24 07:37:36.754661+00
4da8e011-9248-4378-9d6c-16e0cd620017	9c87c06c-6adf-4335-b06b-362512ec62c2	b16b301d-79bb-4d76-b052-bc2183409b6e	active	5	2026-10-23 16:26:39.234987+00
7f13f993-eaf6-4c43-9fde-ac892ec275c5	9c87c06c-6adf-4335-b06b-362512ec62c2	8022ea54-fd44-4c71-ad61-6e52cbe95437	active	7	2026-10-24 12:06:53.285319+00
\.


--
-- Data for Name: tenants; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.tenants (id, name, slug, kind, status, created_at, updated_at) FROM stdin;
9c87c06c-6adf-4335-b06b-362512ec62c2	平台管理租户	platform	consumer	active	2026-10-23 16:26:39.234987+00	2026-10-27 07:45:24.749111+00
fe4a8854-cc40-451d-842a-930a3c816356	演示租户	demo	consumer	active	2026-10-23 16:26:39.234987+00	2026-10-27 07:45:45.684458+00
7acec14b-8ca2-4b3f-a5cd-5920142db325	测试租户	testdemo1	consumer	active	2026-10-27 08:24:19.943802+00	2026-10-27 08:24:25.946521+00
\.


--
-- Data for Name: user_group_memberships; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.user_group_memberships (group_id, membership_id, tenant_id, created_at) FROM stdin;
\.


--
-- Data for Name: user_group_roles; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.user_group_roles (group_id, role_id, tenant_id, created_at) FROM stdin;
\.


--
-- Data for Name: user_groups; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.user_groups (id, tenant_id, key, name, description, status, created_at) FROM stdin;
b9616803-0795-4ebd-a7f6-bcb6dd7c7fee	9c87c06c-6adf-4335-b06b-362512ec62c2	31233123	测试	1323	active	2026-10-27 08:29:34.110744+00
\.


--
-- Data for Name: user_invitations; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.user_invitations (id, tenant_id, role_id, email, display_name, token_hash, expires_at, accepted_at, revoked_at, created_by, created_at) FROM stdin;
33dd4358-5d73-4093-9cad-ee0fba40c5a0	9c87c06c-6adf-4335-b06b-362512ec62c2	c8964ac0-0154-45fa-8062-6cedded4ab6d	1377@qq.com	eq	1e66580729a23048de6a66488c65b51db8cedbb86964242e037b19ddd99c22d3	2026-10-30 08:30:27.099717+00	\N	2026-10-27 11:37:10.696447+00	b16b301d-79bb-4d76-b052-bc2183409b6e	2026-10-27 08:30:27.079854+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: iam
--

COPY public.users (id, email, phone_number, password_hash, display_name, status, auth_version, email_verified_at, phone_verified_at, created_at, updated_at) FROM stdin;
b16b301d-79bb-4d76-b052-bc2183409b6e	admin@example.com	\N	$argon2id$v=19$m=65536,t=3,p=4$4Gdw4fPCL+hRDf/eFYlMeg$TfXUt07byiD7B2vZfJATp7vQouseXP3rnOf+N0xuh1o	平台管理员	active	1	\N	\N	2026-10-23 16:26:39.234987+00	2026-10-23 16:26:39.234987+00
3d84740b-fcc5-401a-89cc-8408ccd004da	l2-admin@demo.example.com	\N	$argon2id$v=19$m=65536,t=3,p=4$s8sTf2e21czkGK+De+DP6A$+VXvIEvMnCCoDAvVNFAULxqdGOM5uqez6FU/CVPvAFU	走查·L2 应用管理员	active	1	\N	\N	2026-10-23 16:53:14.473478+00	2026-10-23 16:53:14.473478+00
08b2ecea-9232-4479-9c47-dbcd2befc0af	l3-admin@demo.example.com	\N	$argon2id$v=19$m=65536,t=3,p=4$R68qJD2oMYjzR/XkqWXN1Q$DmaiGP/r5t3oS/GSSdrXfQaTB/tLrPVj6/j/5rOEJ40	走查·L3 租户管理员	active	1	\N	\N	2026-10-23 16:53:14.473478+00	2026-10-23 16:53:14.473478+00
427efcf4-76a2-4200-8911-807d53aec55b	l4-member@demo.example.com	\N	$argon2id$v=19$m=65536,t=3,p=4$l+O+rNTvLU/dNT2BEIAyhA$+xEZegdkqon+wQlrz/AxUywFKaNV8Mn5d2n31wZTbJg	走查·L4 应用成员	active	1	\N	\N	2026-10-23 16:53:14.473478+00	2026-10-23 16:53:14.473478+00
0691da35-9905-4b03-a3d1-f07578e09ac8	crud-demo@example.com	\N	$argon2id$v=19$m=65536,t=3,p=4$pI+JttEgeosXUd6qP+UGig$07v1HQoF87GVqC5lxVQNH0t9NMJ9MdsXka/jX420sM8	CRUD Demo User	active	1	\N	\N	2026-10-24 07:21:51.645196+00	2026-10-24 07:21:51.645196+00
ad27a767-01c3-44be-9794-ba2e33eb2522	deerflow-demo@example.com	\N	$argon2id$v=19$m=65536,t=3,p=4$NeRKAZflBKKSj48eFxbZYQ$gjUQS21luVPDjJy9C0919ssFwjw2H+1cp2gGiU1JgJI	DeerFlow Demo	active	1	\N	\N	2026-10-24 07:37:36.754661+00	2026-10-24 07:37:36.754661+00
8022ea54-fd44-4c71-ad61-6e52cbe95437	shaohua_code@163.com	\N	$argon2id$v=19$m=65536,t=3,p=4$htZFZ/RQF8sLs9/9oIW9Ww$7x0NAvBhEtt7N/OuqFrf7DikwAoARklzfLLsT0p8d78	刘少华	active	1	\N	\N	2026-10-24 12:06:53.285319+00	2026-10-24 12:06:53.285319+00
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: application_resources application_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.application_resources
    ADD CONSTRAINT application_resources_pkey PRIMARY KEY (id);


--
-- Name: application_themes application_themes_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.application_themes
    ADD CONSTRAINT application_themes_pkey PRIMARY KEY (id);


--
-- Name: applications applications_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);


--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: login_attempt_buckets login_attempt_buckets_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.login_attempt_buckets
    ADD CONSTRAINT login_attempt_buckets_pkey PRIMARY KEY (key_hash);


--
-- Name: membership_organizations membership_organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.membership_organizations
    ADD CONSTRAINT membership_organizations_pkey PRIMARY KEY (membership_id, organization_id);


--
-- Name: model_catalog model_catalog_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_catalog
    ADD CONSTRAINT model_catalog_pkey PRIMARY KEY (id);


--
-- Name: model_usage_events model_usage_events_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_events
    ADD CONSTRAINT model_usage_events_pkey PRIMARY KEY (id);


--
-- Name: model_usage_reservations model_usage_reservations_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_reservations
    ADD CONSTRAINT model_usage_reservations_pkey PRIMARY KEY (id);


--
-- Name: oauth_authorization_codes oauth_authorization_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_authorization_codes
    ADD CONSTRAINT oauth_authorization_codes_pkey PRIMARY KEY (id);


--
-- Name: oauth_consent_requests oauth_consent_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_consent_requests
    ADD CONSTRAINT oauth_consent_requests_pkey PRIMARY KEY (id);


--
-- Name: oauth_refresh_tokens oauth_refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_refresh_tokens
    ADD CONSTRAINT oauth_refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: password_reset_throttles password_reset_throttles_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.password_reset_throttles
    ADD CONSTRAINT password_reset_throttles_pkey PRIMARY KEY (email_hash);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: public_registration_challenges public_registration_challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_challenges
    ADD CONSTRAINT public_registration_challenges_pkey PRIMARY KEY (id);


--
-- Name: public_registration_consents public_registration_consents_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_consents
    ADD CONSTRAINT public_registration_consents_pkey PRIMARY KEY (id);


--
-- Name: public_registration_email_outbox public_registration_email_outbox_challenge_id_key; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_email_outbox
    ADD CONSTRAINT public_registration_email_outbox_challenge_id_key UNIQUE (challenge_id);


--
-- Name: public_registration_email_outbox public_registration_email_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_email_outbox
    ADD CONSTRAINT public_registration_email_outbox_pkey PRIMARY KEY (id);


--
-- Name: public_registration_throttles public_registration_throttles_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_throttles
    ADD CONSTRAINT public_registration_throttles_pkey PRIMARY KEY (bucket_hash);


--
-- Name: refresh_sessions refresh_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.refresh_sessions
    ADD CONSTRAINT refresh_sessions_pkey PRIMARY KEY (id);


--
-- Name: revoked_access_tokens revoked_access_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.revoked_access_tokens
    ADD CONSTRAINT revoked_access_tokens_pkey PRIMARY KEY (jti_hash);


--
-- Name: role_application_resources role_application_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_application_resources
    ADD CONSTRAINT role_application_resources_pkey PRIMARY KEY (role_id, resource_id);


--
-- Name: role_bindings role_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_bindings
    ADD CONSTRAINT role_bindings_pkey PRIMARY KEY (id);


--
-- Name: role_data_scopes role_data_scopes_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_data_scopes
    ADD CONSTRAINT role_data_scopes_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: tenant_memberships tenant_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: application_resources uq_application_resource_app_code; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.application_resources
    ADD CONSTRAINT uq_application_resource_app_code UNIQUE (application_id, code);


--
-- Name: application_themes uq_application_theme_version; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.application_themes
    ADD CONSTRAINT uq_application_theme_version UNIQUE (application_id, version);


--
-- Name: tenant_memberships uq_membership_id_tenant; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT uq_membership_id_tenant UNIQUE (id, tenant_id);


--
-- Name: role_bindings uq_membership_role; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_bindings
    ADD CONSTRAINT uq_membership_role UNIQUE (membership_id, role_id);


--
-- Name: tenant_memberships uq_membership_tenant_user; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT uq_membership_tenant_user UNIQUE (tenant_id, user_id);


--
-- Name: model_catalog uq_model_tenant_key; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_catalog
    ADD CONSTRAINT uq_model_tenant_key UNIQUE (tenant_id, key);


--
-- Name: model_usage_events uq_model_usage_request_id; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_events
    ADD CONSTRAINT uq_model_usage_request_id UNIQUE (request_id);


--
-- Name: model_usage_reservations uq_model_usage_reservation_request_id; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_reservations
    ADD CONSTRAINT uq_model_usage_reservation_request_id UNIQUE (request_id);


--
-- Name: oauth_authorization_codes uq_oauth_authorization_code_hash; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_authorization_codes
    ADD CONSTRAINT uq_oauth_authorization_code_hash UNIQUE (code_hash);


--
-- Name: oauth_consent_requests uq_oauth_consent_request_ticket_hash; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_consent_requests
    ADD CONSTRAINT uq_oauth_consent_request_ticket_hash UNIQUE (ticket_hash);


--
-- Name: oauth_refresh_tokens uq_oauth_refresh_token_hash; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_refresh_tokens
    ADD CONSTRAINT uq_oauth_refresh_token_hash UNIQUE (token_hash);


--
-- Name: organizations uq_organization_id_tenant; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT uq_organization_id_tenant UNIQUE (id, tenant_id);


--
-- Name: organizations uq_organization_tenant_key; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT uq_organization_tenant_key UNIQUE (tenant_id, key);


--
-- Name: password_reset_tokens uq_password_reset_token_hash; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT uq_password_reset_token_hash UNIQUE (token_hash);


--
-- Name: public_registration_challenges uq_registration_app_email; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_challenges
    ADD CONSTRAINT uq_registration_app_email UNIQUE (application_id, email_hash);


--
-- Name: public_registration_consents uq_registration_consent_policy_version; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_consents
    ADD CONSTRAINT uq_registration_consent_policy_version UNIQUE (user_id, application_id, terms_version, privacy_version);


--
-- Name: roles uq_role_id_tenant; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT uq_role_id_tenant UNIQUE (id, tenant_id);


--
-- Name: role_data_scopes uq_role_permission_data_scope; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_data_scopes
    ADD CONSTRAINT uq_role_permission_data_scope UNIQUE (role_id, permission_id);


--
-- Name: user_groups uq_user_group_id_tenant; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_groups
    ADD CONSTRAINT uq_user_group_id_tenant UNIQUE (id, tenant_id);


--
-- Name: user_groups uq_user_group_tenant_key; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_groups
    ADD CONSTRAINT uq_user_group_tenant_key UNIQUE (tenant_id, key);


--
-- Name: user_group_memberships user_group_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_group_memberships
    ADD CONSTRAINT user_group_memberships_pkey PRIMARY KEY (group_id, membership_id);


--
-- Name: user_group_roles user_group_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_group_roles
    ADD CONSTRAINT user_group_roles_pkey PRIMARY KEY (group_id, role_id);


--
-- Name: user_groups user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_groups
    ADD CONSTRAINT user_groups_pkey PRIMARY KEY (id);


--
-- Name: user_invitations user_invitations_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_invitations
    ADD CONSTRAINT user_invitations_pkey PRIMARY KEY (id);


--
-- Name: user_invitations user_invitations_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_invitations
    ADD CONSTRAINT user_invitations_token_hash_key UNIQUE (token_hash);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_application_resources_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_application_resources_application_id ON public.application_resources USING btree (application_id);


--
-- Name: ix_application_resources_parent_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_application_resources_parent_id ON public.application_resources USING btree (parent_id);


--
-- Name: ix_application_themes_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_application_themes_application_id ON public.application_themes USING btree (application_id);


--
-- Name: ix_applications_client_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX ix_applications_client_id ON public.applications USING btree (client_id);


--
-- Name: ix_applications_permission_namespace; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_applications_permission_namespace ON public.applications USING btree (permission_namespace);


--
-- Name: ix_applications_registration_role_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_applications_registration_role_id ON public.applications USING btree (registration_role_id);


--
-- Name: ix_applications_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_applications_tenant_id ON public.applications USING btree (tenant_id);


--
-- Name: ix_audit_events_action; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_audit_events_action ON public.audit_events USING btree (action);


--
-- Name: ix_audit_events_actor_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_audit_events_actor_user_id ON public.audit_events USING btree (actor_user_id);


--
-- Name: ix_audit_events_created_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_audit_events_created_at ON public.audit_events USING btree (created_at);


--
-- Name: ix_audit_events_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_audit_events_tenant_id ON public.audit_events USING btree (tenant_id);


--
-- Name: ix_login_attempt_buckets_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_login_attempt_buckets_expires_at ON public.login_attempt_buckets USING btree (expires_at);


--
-- Name: ix_membership_organizations_organization_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_membership_organizations_organization_id ON public.membership_organizations USING btree (organization_id);


--
-- Name: ix_membership_organizations_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_membership_organizations_tenant_id ON public.membership_organizations USING btree (tenant_id);


--
-- Name: ix_model_catalog_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_catalog_tenant_id ON public.model_catalog USING btree (tenant_id);


--
-- Name: ix_model_usage_events_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_events_application_id ON public.model_usage_events USING btree (application_id);


--
-- Name: ix_model_usage_events_created_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_events_created_at ON public.model_usage_events USING btree (created_at);


--
-- Name: ix_model_usage_events_model_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_events_model_id ON public.model_usage_events USING btree (model_id);


--
-- Name: ix_model_usage_events_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_events_tenant_id ON public.model_usage_events USING btree (tenant_id);


--
-- Name: ix_model_usage_events_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_events_user_id ON public.model_usage_events USING btree (user_id);


--
-- Name: ix_model_usage_reservations_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_reservations_application_id ON public.model_usage_reservations USING btree (application_id);


--
-- Name: ix_model_usage_reservations_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_reservations_expires_at ON public.model_usage_reservations USING btree (expires_at);


--
-- Name: ix_model_usage_reservations_model_expiry; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_reservations_model_expiry ON public.model_usage_reservations USING btree (model_id, expires_at);


--
-- Name: ix_model_usage_reservations_model_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_reservations_model_id ON public.model_usage_reservations USING btree (model_id);


--
-- Name: ix_model_usage_reservations_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_reservations_tenant_id ON public.model_usage_reservations USING btree (tenant_id);


--
-- Name: ix_model_usage_reservations_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_model_usage_reservations_user_id ON public.model_usage_reservations USING btree (user_id);


--
-- Name: ix_oauth_authorization_codes_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_authorization_codes_application_id ON public.oauth_authorization_codes USING btree (application_id);


--
-- Name: ix_oauth_authorization_codes_client_expiry; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_authorization_codes_client_expiry ON public.oauth_authorization_codes USING btree (application_id, expires_at);


--
-- Name: ix_oauth_authorization_codes_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_authorization_codes_expires_at ON public.oauth_authorization_codes USING btree (expires_at);


--
-- Name: ix_oauth_authorization_codes_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_authorization_codes_user_id ON public.oauth_authorization_codes USING btree (user_id);


--
-- Name: ix_oauth_consent_requests_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_consent_requests_application_id ON public.oauth_consent_requests USING btree (application_id);


--
-- Name: ix_oauth_consent_requests_expiry; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_consent_requests_expiry ON public.oauth_consent_requests USING btree (expires_at);


--
-- Name: ix_oauth_consent_requests_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_consent_requests_user_id ON public.oauth_consent_requests USING btree (user_id);


--
-- Name: ix_oauth_refresh_tokens_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_refresh_tokens_application_id ON public.oauth_refresh_tokens USING btree (application_id);


--
-- Name: ix_oauth_refresh_tokens_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_refresh_tokens_expires_at ON public.oauth_refresh_tokens USING btree (expires_at);


--
-- Name: ix_oauth_refresh_tokens_family_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_refresh_tokens_family_id ON public.oauth_refresh_tokens USING btree (family_id);


--
-- Name: ix_oauth_refresh_tokens_family_revoked; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_refresh_tokens_family_revoked ON public.oauth_refresh_tokens USING btree (family_id, revoked_at);


--
-- Name: ix_oauth_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_oauth_refresh_tokens_user_id ON public.oauth_refresh_tokens USING btree (user_id);


--
-- Name: ix_organizations_parent_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_organizations_parent_id ON public.organizations USING btree (parent_id);


--
-- Name: ix_organizations_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_organizations_tenant_id ON public.organizations USING btree (tenant_id);


--
-- Name: ix_password_reset_throttles_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_password_reset_throttles_expires_at ON public.password_reset_throttles USING btree (expires_at);


--
-- Name: ix_password_reset_tokens_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_password_reset_tokens_expires_at ON public.password_reset_tokens USING btree (expires_at);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_permissions_catalog_namespace; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_permissions_catalog_namespace ON public.permissions USING btree (catalog_namespace);


--
-- Name: ix_permissions_code; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX ix_permissions_code ON public.permissions USING btree (code);


--
-- Name: ix_permissions_resource_type; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_permissions_resource_type ON public.permissions USING btree (resource_type);


--
-- Name: ix_public_registration_challenges_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_public_registration_challenges_application_id ON public.public_registration_challenges USING btree (application_id);


--
-- Name: ix_public_registration_challenges_existing_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_public_registration_challenges_existing_user_id ON public.public_registration_challenges USING btree (existing_user_id);


--
-- Name: ix_public_registration_challenges_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_public_registration_challenges_expires_at ON public.public_registration_challenges USING btree (expires_at);


--
-- Name: ix_public_registration_challenges_registration_role_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_public_registration_challenges_registration_role_id ON public.public_registration_challenges USING btree (registration_role_id);


--
-- Name: ix_public_registration_consents_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_public_registration_consents_application_id ON public.public_registration_consents USING btree (application_id);


--
-- Name: ix_public_registration_consents_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_public_registration_consents_user_id ON public.public_registration_consents USING btree (user_id);


--
-- Name: ix_public_registration_throttles_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_public_registration_throttles_expires_at ON public.public_registration_throttles USING btree (expires_at);


--
-- Name: ix_refresh_sessions_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_refresh_sessions_expires_at ON public.refresh_sessions USING btree (expires_at);


--
-- Name: ix_refresh_sessions_token_hash; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX ix_refresh_sessions_token_hash ON public.refresh_sessions USING btree (token_hash);


--
-- Name: ix_refresh_sessions_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_refresh_sessions_user_id ON public.refresh_sessions USING btree (user_id);


--
-- Name: ix_revoked_access_tokens_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_revoked_access_tokens_expires_at ON public.revoked_access_tokens USING btree (expires_at);


--
-- Name: ix_role_application_resources_resource_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_application_resources_resource_id ON public.role_application_resources USING btree (resource_id);


--
-- Name: ix_role_bindings_membership_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_bindings_membership_id ON public.role_bindings USING btree (membership_id);


--
-- Name: ix_role_bindings_role_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_bindings_role_id ON public.role_bindings USING btree (role_id);


--
-- Name: ix_role_data_scopes_permission_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_data_scopes_permission_id ON public.role_data_scopes USING btree (permission_id);


--
-- Name: ix_role_data_scopes_role_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_data_scopes_role_id ON public.role_data_scopes USING btree (role_id);


--
-- Name: ix_role_data_scopes_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_data_scopes_tenant_id ON public.role_data_scopes USING btree (tenant_id);


--
-- Name: ix_role_permissions_permission_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_permissions_permission_id ON public.role_permissions USING btree (permission_id);


--
-- Name: ix_role_permissions_resource_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_permissions_resource_id ON public.role_permissions USING btree (resource_id);


--
-- Name: ix_role_permissions_role_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_role_permissions_role_id ON public.role_permissions USING btree (role_id);


--
-- Name: ix_roles_application_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_roles_application_id ON public.roles USING btree (application_id);


--
-- Name: ix_roles_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_roles_tenant_id ON public.roles USING btree (tenant_id);


--
-- Name: ix_tenant_memberships_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_tenant_memberships_tenant_id ON public.tenant_memberships USING btree (tenant_id);


--
-- Name: ix_tenant_memberships_user_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_tenant_memberships_user_id ON public.tenant_memberships USING btree (user_id);


--
-- Name: ix_tenants_slug; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX ix_tenants_slug ON public.tenants USING btree (slug);


--
-- Name: ix_user_group_memberships_membership_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_group_memberships_membership_id ON public.user_group_memberships USING btree (membership_id);


--
-- Name: ix_user_group_memberships_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_group_memberships_tenant_id ON public.user_group_memberships USING btree (tenant_id);


--
-- Name: ix_user_group_roles_role_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_group_roles_role_id ON public.user_group_roles USING btree (role_id);


--
-- Name: ix_user_group_roles_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_group_roles_tenant_id ON public.user_group_roles USING btree (tenant_id);


--
-- Name: ix_user_groups_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_groups_tenant_id ON public.user_groups USING btree (tenant_id);


--
-- Name: ix_user_invitations_created_by; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_invitations_created_by ON public.user_invitations USING btree (created_by);


--
-- Name: ix_user_invitations_email; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_invitations_email ON public.user_invitations USING btree (email);


--
-- Name: ix_user_invitations_expires_at; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_invitations_expires_at ON public.user_invitations USING btree (expires_at);


--
-- Name: ix_user_invitations_role_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_invitations_role_id ON public.user_invitations USING btree (role_id);


--
-- Name: ix_user_invitations_tenant_id; Type: INDEX; Schema: public; Owner: iam
--

CREATE INDEX ix_user_invitations_tenant_id ON public.user_invitations USING btree (tenant_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_phone_number; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX ix_users_phone_number ON public.users USING btree (phone_number);


--
-- Name: uq_membership_primary_organization; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX uq_membership_primary_organization ON public.membership_organizations USING btree (membership_id) WHERE (is_primary IS TRUE);


--
-- Name: uq_role_app_key; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX uq_role_app_key ON public.roles USING btree (tenant_id, application_id, key) WHERE (application_id IS NOT NULL);


--
-- Name: uq_role_tenant_key; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX uq_role_tenant_key ON public.roles USING btree (tenant_id, key) WHERE (application_id IS NULL);


--
-- Name: uq_user_invitation_pending_email; Type: INDEX; Schema: public; Owner: iam
--

CREATE UNIQUE INDEX uq_user_invitation_pending_email ON public.user_invitations USING btree (tenant_id, email) WHERE ((accepted_at IS NULL) AND (revoked_at IS NULL));


--
-- Name: application_resources application_resources_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.application_resources
    ADD CONSTRAINT application_resources_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: application_resources application_resources_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.application_resources
    ADD CONSTRAINT application_resources_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.application_resources(id) ON DELETE CASCADE;


--
-- Name: application_themes application_themes_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.application_themes
    ADD CONSTRAINT application_themes_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: applications applications_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: audit_events audit_events_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: audit_events audit_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE SET NULL;


--
-- Name: role_data_scopes fk_data_scope_role_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_data_scopes
    ADD CONSTRAINT fk_data_scope_role_tenant FOREIGN KEY (role_id, tenant_id) REFERENCES public.roles(id, tenant_id) ON DELETE CASCADE;


--
-- Name: membership_organizations fk_membership_organization_member_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.membership_organizations
    ADD CONSTRAINT fk_membership_organization_member_tenant FOREIGN KEY (membership_id, tenant_id) REFERENCES public.tenant_memberships(id, tenant_id) ON DELETE CASCADE;


--
-- Name: membership_organizations fk_membership_organization_org_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.membership_organizations
    ADD CONSTRAINT fk_membership_organization_org_tenant FOREIGN KEY (organization_id, tenant_id) REFERENCES public.organizations(id, tenant_id) ON DELETE CASCADE;


--
-- Name: organizations fk_organization_parent_same_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT fk_organization_parent_same_tenant FOREIGN KEY (parent_id, tenant_id) REFERENCES public.organizations(id, tenant_id) ON DELETE RESTRICT;


--
-- Name: user_group_memberships fk_user_group_membership_group_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_group_memberships
    ADD CONSTRAINT fk_user_group_membership_group_tenant FOREIGN KEY (group_id, tenant_id) REFERENCES public.user_groups(id, tenant_id) ON DELETE CASCADE;


--
-- Name: user_group_memberships fk_user_group_membership_member_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_group_memberships
    ADD CONSTRAINT fk_user_group_membership_member_tenant FOREIGN KEY (membership_id, tenant_id) REFERENCES public.tenant_memberships(id, tenant_id) ON DELETE CASCADE;


--
-- Name: user_group_roles fk_user_group_role_group_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_group_roles
    ADD CONSTRAINT fk_user_group_role_group_tenant FOREIGN KEY (group_id, tenant_id) REFERENCES public.user_groups(id, tenant_id) ON DELETE CASCADE;


--
-- Name: user_group_roles fk_user_group_role_role_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_group_roles
    ADD CONSTRAINT fk_user_group_role_role_tenant FOREIGN KEY (role_id, tenant_id) REFERENCES public.roles(id, tenant_id) ON DELETE CASCADE;


--
-- Name: user_invitations fk_user_invitation_role_tenant; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_invitations
    ADD CONSTRAINT fk_user_invitation_role_tenant FOREIGN KEY (role_id, tenant_id) REFERENCES public.roles(id, tenant_id) ON DELETE RESTRICT;


--
-- Name: membership_organizations membership_organizations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.membership_organizations
    ADD CONSTRAINT membership_organizations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: model_catalog model_catalog_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_catalog
    ADD CONSTRAINT model_catalog_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: model_usage_events model_usage_events_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_events
    ADD CONSTRAINT model_usage_events_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE RESTRICT;


--
-- Name: model_usage_events model_usage_events_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_events
    ADD CONSTRAINT model_usage_events_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.model_catalog(id) ON DELETE RESTRICT;


--
-- Name: model_usage_events model_usage_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_events
    ADD CONSTRAINT model_usage_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: model_usage_events model_usage_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_events
    ADD CONSTRAINT model_usage_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: model_usage_reservations model_usage_reservations_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_reservations
    ADD CONSTRAINT model_usage_reservations_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE RESTRICT;


--
-- Name: model_usage_reservations model_usage_reservations_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_reservations
    ADD CONSTRAINT model_usage_reservations_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.model_catalog(id) ON DELETE RESTRICT;


--
-- Name: model_usage_reservations model_usage_reservations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_reservations
    ADD CONSTRAINT model_usage_reservations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: model_usage_reservations model_usage_reservations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.model_usage_reservations
    ADD CONSTRAINT model_usage_reservations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: oauth_authorization_codes oauth_authorization_codes_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_authorization_codes
    ADD CONSTRAINT oauth_authorization_codes_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: oauth_authorization_codes oauth_authorization_codes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_authorization_codes
    ADD CONSTRAINT oauth_authorization_codes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: oauth_consent_requests oauth_consent_requests_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_consent_requests
    ADD CONSTRAINT oauth_consent_requests_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: oauth_consent_requests oauth_consent_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_consent_requests
    ADD CONSTRAINT oauth_consent_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: oauth_refresh_tokens oauth_refresh_tokens_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_refresh_tokens
    ADD CONSTRAINT oauth_refresh_tokens_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: oauth_refresh_tokens oauth_refresh_tokens_replaced_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_refresh_tokens
    ADD CONSTRAINT oauth_refresh_tokens_replaced_by_id_fkey FOREIGN KEY (replaced_by_id) REFERENCES public.oauth_refresh_tokens(id) ON DELETE SET NULL;


--
-- Name: oauth_refresh_tokens oauth_refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.oauth_refresh_tokens
    ADD CONSTRAINT oauth_refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: organizations organizations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: public_registration_challenges public_registration_challenges_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_challenges
    ADD CONSTRAINT public_registration_challenges_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: public_registration_challenges public_registration_challenges_existing_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_challenges
    ADD CONSTRAINT public_registration_challenges_existing_user_id_fkey FOREIGN KEY (existing_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: public_registration_challenges public_registration_challenges_registration_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_challenges
    ADD CONSTRAINT public_registration_challenges_registration_role_id_fkey FOREIGN KEY (registration_role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: public_registration_consents public_registration_consents_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_consents
    ADD CONSTRAINT public_registration_consents_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: public_registration_consents public_registration_consents_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_consents
    ADD CONSTRAINT public_registration_consents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: public_registration_email_outbox public_registration_email_outbox_challenge_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.public_registration_email_outbox
    ADD CONSTRAINT public_registration_email_outbox_challenge_id_fkey FOREIGN KEY (challenge_id) REFERENCES public.public_registration_challenges(id) ON DELETE CASCADE;


--
-- Name: refresh_sessions refresh_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.refresh_sessions
    ADD CONSTRAINT refresh_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: role_application_resources role_application_resources_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_application_resources
    ADD CONSTRAINT role_application_resources_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.application_resources(id) ON DELETE CASCADE;


--
-- Name: role_application_resources role_application_resources_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_application_resources
    ADD CONSTRAINT role_application_resources_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: role_bindings role_bindings_membership_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_bindings
    ADD CONSTRAINT role_bindings_membership_id_fkey FOREIGN KEY (membership_id) REFERENCES public.tenant_memberships(id) ON DELETE CASCADE;


--
-- Name: role_bindings role_bindings_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_bindings
    ADD CONSTRAINT role_bindings_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: role_data_scopes role_data_scopes_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_data_scopes
    ADD CONSTRAINT role_data_scopes_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id) ON DELETE CASCADE;


--
-- Name: role_data_scopes role_data_scopes_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_data_scopes
    ADD CONSTRAINT role_data_scopes_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: roles roles_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE SET NULL;


--
-- Name: roles roles_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_memberships tenant_memberships_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_memberships tenant_memberships_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_group_memberships user_group_memberships_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_group_memberships
    ADD CONSTRAINT user_group_memberships_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: user_group_roles user_group_roles_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_group_roles
    ADD CONSTRAINT user_group_roles_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: user_groups user_groups_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_groups
    ADD CONSTRAINT user_groups_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: user_invitations user_invitations_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_invitations
    ADD CONSTRAINT user_invitations_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: user_invitations user_invitations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: iam
--

ALTER TABLE ONLY public.user_invitations
    ADD CONSTRAINT user_invitations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict gw2pJ0WNxCnBAY8P8IBlQmDR6uv0DLyTRKWqYsuF0qlGetdYI2Vqd7XT8ejwseE

