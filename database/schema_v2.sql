-- =============================================================================
-- FindMyNyumba — Target Production Schema (PostgreSQL 14+ / Supabase)
-- Senior PostgreSQL Database Architect
--
-- This is the DESIGN TARGET, not a drop-in migration. It shows the correct
-- types, keys, foreign keys (with explicit ON DELETE), constraints, and indexes
-- for a platform meant to scale to Zambia's largest accommodation marketplace.
--
-- To adopt on a LIVE database, follow the migration sequence in
-- BACKEND_DB_REVIEW.md (§9): add constraints NOT VALID then VALIDATE, build
-- indexes CONCURRENTLY, and migrate data (reviews->listings, float->numeric)
-- deliberately — do NOT run this file against production as-is.
--
-- Design principles applied:
--   * Money is NUMERIC(12,2), never float.
--   * BIGINT identity on high-volume tables; INTEGER on small dimensions.
--   * Every FK has an explicit ON DELETE policy.
--   * Small enums enforced with CHECK constraints (portable, no native-enum
--     migration pain); large lookups use dimension tables.
--   * Soft-delete (deleted_at) on user-facing entities; financial/audit rows
--     are never hard-deleted.
--   * Composite/partial indexes match the application's real query paths.
--   * Append-only giants are partitioned by month on created_at.
-- =============================================================================

-- ---------- Extensions -------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS citext;      -- case-insensitive email
CREATE EXTENSION IF NOT EXISTS postgis;     -- geo radius search (optional but recommended)
-- CREATE EXTENSION IF NOT EXISTS pg_partman; -- optional: automated partition mgmt

-- ---------- Shared updated_at trigger ---------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- DIMENSION / LOOKUP TABLES
-- =============================================================================

CREATE TABLE institutions (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    town        TEXT,
    type        TEXT CHECK (type IN ('university','college','tevet')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_institutions_name_town ON institutions (lower(name), lower(coalesce(town,'')));

-- =============================================================================
-- USERS  (single identity table; role as constrained string)
-- =============================================================================

CREATE TABLE users (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name          TEXT NOT NULL,
    email              CITEXT NOT NULL,                       -- case-insensitive
    hashed_password    TEXT NOT NULL,
    role               TEXT NOT NULL DEFAULT 'student'
                         CHECK (role IN ('student','student_host','landlord','admin')),
    phone_number       TEXT,
    avatar_url         TEXT,

    -- landlord / host profile
    business_name      TEXT,
    business_location  TEXT,
    id_number          TEXT,                                  -- NRC

    -- verification (documents now live in verification_documents)
    verification_status TEXT NOT NULL DEFAULT 'unverified'
                         CHECK (verification_status IN ('unverified','pending','verified','rejected')),
    verification_rejection_reason TEXT,

    -- flags / prefs
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified        BOOLEAN NOT NULL DEFAULT FALSE,         -- email verified
    email_alerts       BOOLEAN NOT NULL DEFAULT TRUE,
    sms_alerts         BOOLEAN NOT NULL DEFAULT FALSE,

    -- auth security
    last_login            TIMESTAMPTZ,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    lockout_until         TIMESTAMPTZ,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at         TIMESTAMPTZ                             -- soft delete
);

-- email unique & case-insensitive (CITEXT makes the unique index CI automatically)
CREATE UNIQUE INDEX uq_users_email ON users (email) WHERE deleted_at IS NULL;
-- one NRC = one account (only enforced where an NRC is supplied)
CREATE UNIQUE INDEX uq_users_id_number ON users (id_number) WHERE id_number IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX ix_users_phone ON users (phone_number);
-- admin verification queue: pending landlords/hosts
CREATE INDEX ix_users_pending_verif ON users (role) WHERE verification_status = 'pending';

CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- VERIFICATION DOCUMENTS  (1-to-many, auditable — replaces the 2 URL columns)
-- =============================================================================

CREATE TABLE verification_documents (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doc_type    TEXT NOT NULL CHECK (doc_type IN ('id','ownership','other')),
    url         TEXT NOT NULL,                  -- Cloudinary delivery URL
    public_id   TEXT,                           -- Cloudinary id for deletion
    status      TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','approved','rejected')),
    reviewed_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_verifdocs_user ON verification_documents (user_id);
CREATE INDEX ix_verifdocs_status ON verification_documents (status, created_at);

-- =============================================================================
-- PASSWORD RESET TOKENS  (single source of truth; drop users.reset_token_*)
-- =============================================================================

CREATE TABLE password_reset_tokens (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,                  -- SHA-256 hex of raw token
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_prt_token_hash ON password_reset_tokens (token_hash);
-- find a user's live (unused, unexpired) tokens fast
CREATE INDEX ix_prt_active ON password_reset_tokens (user_id) WHERE used = FALSE;

-- =============================================================================
-- LISTINGS  (core inventory)
-- =============================================================================

CREATE TABLE listings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    price           NUMERIC(12,2) NOT NULL CHECK (price >= 0),   -- ZMW, NOT float
    location        TEXT NOT NULL,
    listing_type    TEXT CHECK (listing_type IN ('room','bedspace','self_contained','house','flat')),
    nearest_institution TEXT,                    -- or institution_id BIGINT REFERENCES institutions
    image_url       TEXT,                        -- legacy cover; media table is canonical

    status          TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','active','rejected','suspended','hidden')),
    availability_status TEXT NOT NULL DEFAULT 'available'
                     CHECK (availability_status IN ('available','taken')),
    total_spots     INTEGER NOT NULL DEFAULT 1 CHECK (total_spots >= 1),
    available_spots INTEGER NOT NULL DEFAULT 1
                     CHECK (available_spots >= 0 AND available_spots <= total_spots),
    is_boosted      BOOLEAN NOT NULL DEFAULT FALSE,

    -- geo: keep raw coords AND a PostGIS point for indexed radius search
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    geom            geography(Point, 4326),       -- populated from lat/lng

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

-- Browse hot paths (campus search + default sorted feed). Partial on live rows.
CREATE INDEX ix_listings_browse ON listings (status, nearest_institution, price)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_listings_feed ON listings (status, is_boosted DESC, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_listings_owner ON listings (owner_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_listings_title_trgm ON listings USING gin (title gin_trgm_ops); -- needs pg_trgm
-- geo radius search (ST_DWithin uses this)
CREATE INDEX ix_listings_geom ON listings USING gist (geom) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_listings_updated BEFORE UPDATE ON listings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Keep geom in sync with lat/lng automatically
CREATE OR REPLACE FUNCTION listings_sync_geom()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_listings_geom BEFORE INSERT OR UPDATE OF latitude, longitude ON listings
    FOR EACH ROW EXECUTE FUNCTION listings_sync_geom();

-- =============================================================================
-- LISTING MEDIA  (already well-modelled; reproduced with explicit constraints)
-- =============================================================================

CREATE TABLE listing_media (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    listing_id    BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    media_url     TEXT NOT NULL,
    public_id     TEXT,
    resource_type TEXT,
    media_type    TEXT NOT NULL DEFAULT 'photo' CHECK (media_type IN ('photo','video')),
    file_name     TEXT,
    file_size     BIGINT,
    mime_type     TEXT,
    width         INTEGER,
    height        INTEGER,
    duration      DOUBLE PRECISION,
    position      INTEGER NOT NULL DEFAULT 0,
    is_cover      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_media_listing ON listing_media (listing_id, position);
-- at most one cover per listing
CREATE UNIQUE INDEX uq_media_one_cover ON listing_media (listing_id) WHERE is_cover;
CREATE TRIGGER trg_media_updated BEFORE UPDATE ON listing_media
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- SAVED LISTINGS  (junction; unique pair already correct in your model)
-- =============================================================================

CREATE TABLE saved_listings (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id  BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_student_listing UNIQUE (student_id, listing_id)
);
CREATE INDEX ix_saved_student ON saved_listings (student_id);

-- =============================================================================
-- REVIEWS  (FIXED: points at listings; moderated; one per user per listing)
-- =============================================================================

CREATE TABLE reviews (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    listing_id  BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating      SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT,
    status      TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','published','rejected')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_review_user_listing UNIQUE (listing_id, user_id)  -- anti review-bomb
);
CREATE INDEX ix_reviews_listing_pub ON reviews (listing_id) WHERE status = 'published';

-- =============================================================================
-- REPORTS  (abuse/scam workflow)
-- =============================================================================

CREATE TABLE reports (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporter_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id       BIGINT REFERENCES listings(id) ON DELETE SET NULL,
    reported_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    reason           TEXT NOT NULL
                      CHECK (reason IN ('scam','misleading','harassment','duplicate','other')),
    description      TEXT,
    status           TEXT NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open','investigating','reviewed','resolved','dismissed')),
    admin_note       TEXT,
    resolution       TEXT,
    handled_by       BIGINT REFERENCES users(id) ON DELETE SET NULL,
    handled_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- a report must target a listing or a user (or both)
    CONSTRAINT ck_report_target CHECK (listing_id IS NOT NULL OR reported_user_id IS NOT NULL)
);
CREATE INDEX ix_reports_queue ON reports (status, created_at);   -- admin queue
CREATE INDEX ix_reports_listing ON reports (listing_id);
CREATE INDEX ix_reports_reported_user ON reports (reported_user_id);
CREATE INDEX ix_reports_handler ON reports (handled_by);

-- =============================================================================
-- TRANSACTIONS  (money — NUMERIC, constrained state machine)
-- =============================================================================

CREATE TABLE transactions (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ref          TEXT NOT NULL UNIQUE,                          -- 'TXN-000123'
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    listing_id   BIGINT REFERENCES listings(id) ON DELETE SET NULL,
    type         TEXT NOT NULL CHECK (type IN ('deposit','boost','refund','payout','fee')),
    amount       NUMERIC(12,2) NOT NULL CHECK (amount > 0),     -- ZMW, NOT float
    currency     TEXT NOT NULL DEFAULT 'ZMW' CHECK (currency = 'ZMW'),
    method       TEXT NOT NULL CHECK (method IN ('airtel_money','mtn_momo','zamtel','bank','card')),
    status       TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','success','failed','refunded','reversed')),
    provider_ref TEXT,                                          -- mobile-money/bank ref
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_txn_user_status ON transactions (user_id, status);
CREATE INDEX ix_txn_status_created ON transactions (status, created_at);  -- revenue/recon
CREATE TRIGGER trg_txn_updated BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- ESCROW  (deposit held between student and landlord)
-- =============================================================================

CREATE TABLE escrow (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ref            TEXT NOT NULL UNIQUE,
    txn_id         BIGINT REFERENCES transactions(id) ON DELETE SET NULL,
    student_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    landlord_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    listing_id     BIGINT NOT NULL REFERENCES listings(id) ON DELETE RESTRICT,
    amount         NUMERIC(12,2) NOT NULL CHECK (amount > 0),   -- ZMW, NOT float
    status         TEXT NOT NULL DEFAULT 'waiting'
                    CHECK (status IN ('waiting','held','released','refunded','disputed')),
    dispute_reason TEXT,
    held_at        TIMESTAMPTZ,
    released_at    TIMESTAMPTZ,
    refunded_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_escrow_landlord ON escrow (landlord_id, status);
CREATE INDEX ix_escrow_student  ON escrow (student_id, status);
CREATE INDEX ix_escrow_queue    ON escrow (status, created_at);  -- disputes/held oldest first

-- =============================================================================
-- NOTIFICATIONS  (high-volume; partitioned by month; unread partial index)
-- =============================================================================

CREATE TABLE notifications (
    id         BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,  -- null = system-wide
    type       TEXT NOT NULL CHECK (type IN ('report','verification','payment','escrow','listing','message','system')),
    title      TEXT NOT NULL,
    body       TEXT,
    channel    TEXT NOT NULL DEFAULT 'in_app' CHECK (channel IN ('in_app','email','sms')),
    read_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)                                -- PK must include partition key
) PARTITION BY RANGE (created_at);

-- unread badge: WHERE user_id=? AND read_at IS NULL
CREATE INDEX ix_notif_unread ON notifications (user_id) WHERE read_at IS NULL;
-- Example monthly partitions (automate with pg_partman or a cron):
CREATE TABLE notifications_2026_06 PARTITION OF notifications
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE notifications_2026_07 PARTITION OF notifications
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

-- =============================================================================
-- MESSAGES  (high-volume chat; partitioned by month)
-- =============================================================================

CREATE TABLE messages (
    id              BIGINT GENERATED ALWAYS AS IDENTITY,
    sender_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id      BIGINT REFERENCES listings(id) ON DELETE SET NULL,  -- was property_id
    content         TEXT NOT NULL,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    attachment_url  TEXT,
    attachment_name TEXT,
    attachment_type TEXT CHECK (attachment_type IN ('image','file')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- inbox unread count: WHERE receiver_id=? AND is_read=false
CREATE INDEX ix_msg_inbox_unread ON messages (receiver_id) WHERE is_read = FALSE;
-- thread fetch: a conversation between two users about a listing, time-ordered
CREATE INDEX ix_msg_thread ON messages (sender_id, receiver_id, listing_id, created_at);
CREATE INDEX ix_msg_thread_rev ON messages (receiver_id, sender_id, listing_id, created_at);

CREATE TABLE messages_2026_06 PARTITION OF messages
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE messages_2026_07 PARTITION OF messages
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

-- =============================================================================
-- LISTING EVENTS  (analytics firehose; partitioned by month)
-- =============================================================================

CREATE TABLE listing_events (
    id         BIGINT GENERATED ALWAYS AS IDENTITY,
    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('view','contact','save','boost_click')),
    actor_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,  -- null = anonymous
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- funnel query: counts by (listing_id, kind) over a time window
CREATE INDEX ix_events_funnel ON listing_events (listing_id, kind, created_at);

CREATE TABLE listing_events_2026_06 PARTITION OF listing_events
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE listing_events_2026_07 PARTITION OF listing_events
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

-- =============================================================================
-- AUDIT LOGS  (append-only; JSONB meta; partitioned by month)
-- =============================================================================

CREATE TABLE audit_logs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY,
    actor_id    BIGINT REFERENCES users(id) ON DELETE SET NULL,  -- keep log if actor deleted
    actor_role  TEXT,
    action      TEXT NOT NULL,                 -- 'listing.approve', 'message.scam_signal'
    entity_type TEXT,
    entity_id   TEXT,
    ip_address  INET,                          -- proper type, not TEXT
    user_agent  TEXT,
    meta        JSONB,                         -- queryable, not opaque TEXT
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE INDEX ix_audit_entity ON audit_logs (entity_type, entity_id, created_at);
CREATE INDEX ix_audit_action ON audit_logs (action, created_at);
CREATE INDEX ix_audit_actor  ON audit_logs (actor_id, created_at);
-- query inside meta (e.g. scam-signal risk): GIN on JSONB
CREATE INDEX ix_audit_meta ON audit_logs USING gin (meta);

CREATE TABLE audit_logs_2026_06 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE audit_logs_2026_07 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

-- =============================================================================
-- ANALYTICS  (don't aggregate the firehose live)
-- Materialized view: per-listing funnel counts, refreshed on a schedule.
-- =============================================================================

CREATE MATERIALIZED VIEW mv_listing_funnel AS
SELECT
    listing_id,
    count(*) FILTER (WHERE kind = 'view')    AS views,
    count(*) FILTER (WHERE kind = 'contact') AS contacts,
    count(*) FILTER (WHERE kind = 'save')    AS saves,
    max(created_at)                          AS last_event_at
FROM listing_events
GROUP BY listing_id
WITH NO DATA;

CREATE UNIQUE INDEX ix_mv_funnel_listing ON mv_listing_funnel (listing_id);
-- Refresh on a cron (every few minutes): REFRESH MATERIALIZED VIEW CONCURRENTLY mv_listing_funnel;

-- =============================================================================
-- NOTES
-- * Partitioning: create future partitions ahead of time (pg_partman automates
--   this). Retention = DETACH + DROP old partitions (instant vs giant DELETE).
-- * Route heavy admin/analytics reads to a Supabase read replica.
-- * pg_trgm is required for the title trigram index:  CREATE EXTENSION pg_trgm;
-- * If you prefer not to adopt PostGIS yet, drop geom + its trigger/index and
--   use a bounding-box pre-filter on (latitude, longitude) with a btree index,
--   then refine with haversine in the app. PostGIS is the scalable answer.
-- =============================================================================
