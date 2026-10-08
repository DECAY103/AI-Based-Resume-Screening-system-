-- migrations/002_activity_logs_and_reset.sql
-- Adds activity logging, last-login tracking, and email-based password reset.

-- ─── last_login_at on users ──────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;

-- ─── activity_logs ───────────────────────────────────────────────────────────
-- Immutable append-only audit trail for all security-relevant events.
CREATE TABLE IF NOT EXISTS activity_logs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        REFERENCES users(id) ON DELETE SET NULL,
    email       TEXT,
    action      TEXT        NOT NULL,
    detail      TEXT,
    ip_address  TEXT,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_logs_user
    ON activity_logs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_logs_action
    ON activity_logs (action, created_at DESC);

-- ─── password_reset_tokens ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT        NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_reset_token
    ON password_reset_tokens (token) WHERE used = FALSE;
