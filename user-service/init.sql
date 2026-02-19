-- User Service — users_db schema

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    password_hash TEXT NOT NULL,
    credit_balance NUMERIC(10, 2) DEFAULT 0.00,
    two_fa_secret TEXT,
    is_flagged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed Data
-- Password hash for 'password123' (bcrypt)
-- User 1: Normal user
INSERT INTO users (user_id, email, phone, password_hash, credit_balance, is_flagged) VALUES
('41414141-4141-4141-4141-414141414141', 'user1@example.com', '+6591234567', '$2b$12$lzV.N8qX.p1.q1.q1.q1.u1', 1000.00, FALSE)
ON CONFLICT (email) DO NOTHING;

-- User 2: Flagged user (high risk)
INSERT INTO users (user_id, email, phone, password_hash, credit_balance, is_flagged) VALUES
('42424242-4242-4242-4242-424242424242', 'user2@example.com', '+6598765432', '$2b$12$lzV.N8qX.p1.q1.q1.q1.u2', 500.00, TRUE)
ON CONFLICT (email) DO NOTHING;
