-- Inventory Service — seats_db schema

-- Enum Types
DO $$ BEGIN
    CREATE TYPE seat_status AS ENUM ('AVAILABLE', 'HELD', 'SOLD', 'CHECKED_IN');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE entry_result AS ENUM ('SUCCESS', 'DUPLICATE', 'WRONG_HALL', 'UNPAID', 'NOT_FOUND', 'EXPIRED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Seats Table
CREATE TABLE IF NOT EXISTS seats (
    seat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL, -- References events_db (logical FK)
    owner_user_id UUID, -- References users_db (logical FK)
    status seat_status NOT NULL DEFAULT 'AVAILABLE',
    held_by_user_id UUID,
    held_until TIMESTAMP,
    qr_code_hash TEXT,
    price_paid NUMERIC(10, 2),
    row_number VARCHAR(4) NOT NULL,
    seat_number INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Entry Logs Table
CREATE TABLE IF NOT EXISTS entry_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seat_id UUID REFERENCES seats(seat_id),
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scanned_by_staff_id UUID,
    result entry_result NOT NULL,
    hall_id_presented VARCHAR(20),
    hall_id_expected VARCHAR(20)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_seats_event_id ON seats(event_id);
CREATE INDEX IF NOT EXISTS idx_seats_owner_user_id ON seats(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_entry_logs_seat_id ON entry_logs(seat_id);

-- ═══════════════════════════════════════════════════════════════
-- Seed Data — See SEED_DATA.md at project root for full reference
-- ═══════════════════════════════════════════════════════════════
-- Event UUID: e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1 (must match event-service seed)
-- Seat UUID pattern: 55555555-5555-5555-5555-5555555551XX
INSERT INTO seats (seat_id, event_id, row_number, seat_number, status) VALUES
('55555555-5555-5555-5555-555555555101', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'A', 1, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555102', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'A', 2, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555103', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'A', 3, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555104', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'A', 4, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555105', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'A', 5, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555106', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'B', 1, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555107', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'B', 2, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555108', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'B', 3, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555109', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'B', 4, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555110', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'B', 5, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555111', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'C', 1, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555112', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'C', 2, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555113', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'C', 3, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555114', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'C', 4, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555115', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'C', 5, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555116', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'D', 1, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555117', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'D', 2, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555118', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'D', 3, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555119', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'D', 4, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555120', 'e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'D', 5, 'AVAILABLE')
ON CONFLICT (seat_id) DO NOTHING;
