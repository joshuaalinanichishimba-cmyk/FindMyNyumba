-- ============================================================================
-- FindMyNyumba — Trust & Safety schema (PostgreSQL / Supabase)
-- ----------------------------------------------------------------------------
-- This is the production DDL that mirrors app/models/trust_models.py.
--
-- You do NOT have to run this by hand in the normal dev cycle: importing the
-- trust models before Base.metadata.create_all() (see the wiring snippet in
-- TRUST_SAFETY_IMPLEMENTATION.md) creates the tables automatically on startup.
--
-- This file exists for two reasons:
--   1. It is the source of truth for the production database, reviewable in one
--      place by anyone (including a future hire) without reading SQLAlchemy.
--   2. It carries the one thing create_all() CANNOT express: the append-only
--      trigger on audit_logs that enforces "nothing should be deletable".
--
-- Everything here is idempotent (IF NOT EXISTS / CREATE OR REPLACE), so it is
-- safe to run against an existing database. It only ADDS the trust tables and
-- the audit guard; it never drops or rewrites your existing tables.
--
-- Apply on Supabase:  SQL Editor -> paste -> Run
-- Apply via psql:     psql "$DATABASE_URL" -f app/db/trust_schema.sql
-- ============================================================================

BEGIN;

-- ── verifications ───────────────────────────────────────────────────────────
-- One row per verification *case*. A landlord who is rejected and re-applies
-- gets a new row, preserving full history. The current decision is mirrored
-- onto users.verification_status for fast reads elsewhere.
CREATE TABLE IF NOT EXISTS verifications (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),

    phone_verified          BOOLEAN NOT NULL DEFAULT FALSE,
    email_verified          BOOLEAN NOT NULL DEFAULT FALSE,
    nrc_front_uploaded      BOOLEAN NOT NULL DEFAULT FALSE,
    nrc_back_uploaded       BOOLEAN NOT NULL DEFAULT FALSE,
    selfie_uploaded         BOOLEAN NOT NULL DEFAULT FALSE,
    property_docs_uploaded  BOOLEAN NOT NULL DEFAULT FALSE,

    -- pending | review | approved | rejected
    status                  VARCHAR NOT NULL DEFAULT 'pending',
    rejection_reason        TEXT,

    reviewed_by             INTEGER REFERENCES users(id),
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_verifications_user_id ON verifications(user_id);
CREATE INDEX IF NOT EXISTS ix_verifications_status  ON verifications(status);

-- ── verification_documents ──────────────────────────────────────────────────
-- Each uploaded artifact (NRC front/back, selfie, property doc) is its own row,
-- pointing at a Cloudinary secure_url. Raw bytes are NEVER stored in Postgres.
-- phash is the perceptual hash used to catch the same NRC/selfie reused across
-- multiple "landlord" accounts.
CREATE TABLE IF NOT EXISTS verification_documents (
    id                  SERIAL PRIMARY KEY,
    verification_id     INTEGER NOT NULL REFERENCES verifications(id),
    user_id             INTEGER NOT NULL REFERENCES users(id),

    -- nrc_front | nrc_back | selfie | property_doc
    doc_type            VARCHAR NOT NULL,
    file_url            VARCHAR NOT NULL,          -- Cloudinary secure_url
    mime_type           VARCHAR,
    phash               VARCHAR,

    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_verification_documents_verification_id ON verification_documents(verification_id);
CREATE INDEX IF NOT EXISTS ix_verification_documents_user_id        ON verification_documents(user_id);
CREATE INDEX IF NOT EXISTS ix_verification_documents_doc_type       ON verification_documents(doc_type);
CREATE INDEX IF NOT EXISTS ix_verification_documents_phash          ON verification_documents(phash);

-- ── property_verifications ──────────────────────────────────────────────────
-- A listing-level review: are the photos real, does the location check out, are
-- the ownership documents valid. Distinct from the listing's admin
-- approve/reject (which only governs whether it can go live at all).
CREATE TABLE IF NOT EXISTS property_verifications (
    id                  SERIAL PRIMARY KEY,
    listing_id          INTEGER NOT NULL REFERENCES listings(id),
    submitted_by        INTEGER REFERENCES users(id),

    -- NULL = reviewer has not checked this dimension yet.
    photos_ok           BOOLEAN,
    location_ok         BOOLEAN,
    documents_ok        BOOLEAN,

    -- pending | verified | rejected
    status              VARCHAR NOT NULL DEFAULT 'pending',
    rejection_reason    TEXT,

    reviewed_by         INTEGER REFERENCES users(id),
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_property_verifications_listing_id ON property_verifications(listing_id);
CREATE INDEX IF NOT EXISTS ix_property_verifications_status     ON property_verifications(status);

-- ── fraud_reports ───────────────────────────────────────────────────────────
-- Structured Trust & Safety report. The legacy `reports` table stays for
-- backward compatibility; new listing/landlord scam reports flow through here
-- with the richer category set and the
-- Submitted -> Assigned -> Investigating -> Resolved workflow.
CREATE TABLE IF NOT EXISTS fraud_reports (
    id                  SERIAL PRIMARY KEY,
    reporter_id         INTEGER REFERENCES users(id),
    listing_id          INTEGER REFERENCES listings(id),
    reported_user_id    INTEGER REFERENCES users(id),

    -- scam | fake_photos | wrong_location | fake_landlord |
    -- viewing_fee_request | agent_fee_scam | other
    category            VARCHAR NOT NULL,
    description         TEXT,

    -- submitted | assigned | investigating | resolved
    status              VARCHAR NOT NULL DEFAULT 'submitted',
    resolution          TEXT,

    assigned_to         INTEGER REFERENCES users(id),
    assigned_at         TIMESTAMPTZ,
    resolved_by         INTEGER REFERENCES users(id),
    resolved_at         TIMESTAMPTZ,

    ip_address          VARCHAR,                  -- captured for abuse-tracing
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_fraud_reports_reporter_id      ON fraud_reports(reporter_id);
CREATE INDEX IF NOT EXISTS ix_fraud_reports_listing_id       ON fraud_reports(listing_id);
CREATE INDEX IF NOT EXISTS ix_fraud_reports_reported_user_id ON fraud_reports(reported_user_id);
CREATE INDEX IF NOT EXISTS ix_fraud_reports_category         ON fraud_reports(category);
CREATE INDEX IF NOT EXISTS ix_fraud_reports_status           ON fraud_reports(status);
CREATE INDEX IF NOT EXISTS ix_fraud_reports_assigned_to      ON fraud_reports(assigned_to);
-- Composite index that powers the admin queue ("open reports, oldest first").
CREATE INDEX IF NOT EXISTS ix_fraud_reports_status_created   ON fraud_reports(status, created_at);

-- ── risk_scores ─────────────────────────────────────────────────────────────
-- One current row per user (and optionally per listing). Recomputed by
-- app.core.risk_engine on every verification decision / report / listing
-- change. Stored so the admin queue can sort by risk without recomputing on
-- each page load. score is 0-100, HIGHER = SAFER.
CREATE TABLE IF NOT EXISTS risk_scores (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id),
    listing_id  INTEGER REFERENCES listings(id),

    score       INTEGER NOT NULL DEFAULT 50,
    band        VARCHAR NOT NULL DEFAULT 'medium',   -- high | medium | low
    factors     TEXT,                                -- JSON breakdown

    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_risk_scores_user_id    ON risk_scores(user_id);
CREATE INDEX IF NOT EXISTS ix_risk_scores_listing_id ON risk_scores(listing_id);
CREATE INDEX IF NOT EXISTS ix_risk_scores_score      ON risk_scores(score);
CREATE INDEX IF NOT EXISTS ix_risk_scores_band       ON risk_scores(band);

-- ── trust_banners ───────────────────────────────────────────────────────────
-- Admin-editable rotating safety messages. The frontend pulls active banners
-- and rotates them client-side; storing copy here means it can change without
-- a redeploy.
CREATE TABLE IF NOT EXISTS trust_banners (
    id          SERIAL PRIMARY KEY,
    message     VARCHAR NOT NULL,
    level       VARCHAR NOT NULL DEFAULT 'info',     -- info | warning | success
    icon        VARCHAR,
    -- comma-separated page keys, or "all"
    -- e.g. "home,listings,property,dashboard_student,dashboard_landlord"
    pages       VARCHAR NOT NULL DEFAULT 'all',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,

    created_by  INTEGER REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_trust_banners_is_active ON trust_banners(is_active);

-- Seed the five default banners the brief asks for, but ONLY if the table is
-- empty (so re-running this file never duplicates them). The API also ships
-- these as a hard-coded fallback, so an empty table still shows banners.
INSERT INTO trust_banners (message, level, icon, pages, sort_order, is_active)
SELECT * FROM (VALUES
    ('Never pay before physically viewing a property.',        'success', '🟢', 'all', 1, TRUE),
    ('FindMyNyumba does not support viewing fees.',            'success', '🟢', 'all', 2, TRUE),
    ('Report suspicious listings immediately.',                 'warning', '🟢', 'all', 3, TRUE),
    ('Verify landlord badges before sending money.',            'success', '🟢', 'all', 4, TRUE),
    ('Always inspect accommodation before making payment.',     'success', '🟢', 'all', 5, TRUE)
) AS seed(message, level, icon, pages, sort_order, is_active)
WHERE NOT EXISTS (SELECT 1 FROM trust_banners);

-- ============================================================================
-- audit_logs — append-only guard
-- ----------------------------------------------------------------------------
-- The audit_logs table itself already exists (created by admin_models.AuditLog
-- / create_all). We do NOT recreate it here. What we add is the database-level
-- enforcement of the brief's hard requirement: "Nothing should be deletable."
--
-- Application code only ever INSERTs audit rows, but a guarantee that lives in
-- the app can be bypassed by anyone with a DB connection. This trigger makes
-- the database itself reject every UPDATE and DELETE on audit_logs, so the log
-- is genuinely append-only — even a compromised app account or a careless
-- console session cannot rewrite history.
--
-- (If you ever need to prune for storage, do it by archiving to cold storage
-- and TRUNCATE under a maintenance role — TRUNCATE is intentionally not blocked
-- here — never by row-level DELETE.)
-- ============================================================================
CREATE OR REPLACE FUNCTION fmn_audit_logs_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only: % is not permitted', TG_OP
        USING ERRCODE = 'insufficient_privilege';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'audit_logs') THEN
        -- Drop first so the file stays idempotent, then (re)create.
        DROP TRIGGER IF EXISTS trg_audit_logs_no_update ON audit_logs;
        DROP TRIGGER IF EXISTS trg_audit_logs_no_delete ON audit_logs;

        CREATE TRIGGER trg_audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION fmn_audit_logs_append_only();

        CREATE TRIGGER trg_audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION fmn_audit_logs_append_only();
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Optional hardening you can layer on later (left as comments — review before
-- enabling, as they depend on how your Supabase roles are set up):
--
--   -- Make verification document URLs unreadable to the anon role so only the
--   -- service key (your FastAPI backend) can read them:
--   -- ALTER TABLE verification_documents ENABLE ROW LEVEL SECURITY;
--
--   -- Enforce a single "current" risk row per user instead of a history trail:
--   -- CREATE UNIQUE INDEX uq_risk_scores_user ON risk_scores(user_id)
--   --     WHERE listing_id IS NULL;
-- ============================================================================
