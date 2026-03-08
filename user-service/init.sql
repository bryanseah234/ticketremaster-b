-- User Service — users_db schema

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    password_hash TEXT NOT NULL,
    credit_balance NUMERIC(10, 2) DEFAULT 0.00,
    two_fa_secret TEXT,
    is_flagged BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════════
-- Seed Data — See SEED_DATA.md at project root for full reference
-- ═══════════════════════════════════════════════════════════════
-- PLAINTEXT PASSWORD (for both users): password123
-- OTP MOCK CODE: 123456
-- ═══════════════════════════════════════════════════════════════

-- User 1: Normal user (not flagged, $1000 credits)
INSERT INTO users (user_id, email, phone, password_hash, credit_balance, is_flagged, is_admin, is_verified) VALUES
('41414141-4141-4141-4141-414141414141', 'user1@example.com', '+6591234567', '$2b$12$jrGHdU5VKmHxpbehPaEre.DpfqNFf1Ttp.iLuXOamz92RBVn4nONS', 1000.00, FALSE, FALSE, TRUE)
ON CONFLICT (email) DO NOTHING;

-- User 2: High-risk / Flagged user ($500 credits, triggers OTP flow)
INSERT INTO users (user_id, email, phone, password_hash, credit_balance, is_flagged, is_admin, is_verified) VALUES
('42424242-4242-4242-4242-424242424242', 'user2@example.com', '+6598765432', '$2b$12$jrGHdU5VKmHxpbehPaEre.DpfqNFf1Ttp.iLuXOamz92RBVn4nONS', 500.00, TRUE, FALSE, TRUE)
ON CONFLICT (email) DO NOTHING;

-- User 3: Admin user
INSERT INTO users (user_id, email, phone, password_hash, credit_balance, is_flagged, is_admin, is_verified) VALUES
('43434343-4343-4343-4343-434343434343', 'admin@example.com', '+6588888888', '$2b$12$jrGHdU5VKmHxpbehPaEre.DpfqNFf1Ttp.iLuXOamz92RBVn4nONS', 0.00, FALSE, TRUE, TRUE)
ON CONFLICT (email) DO NOTHING;
