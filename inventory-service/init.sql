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

-- Seed Data
-- Hardcoded UUIDs for consistency with other services
-- Event ID: e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1 (Taylor Swift Eras Tour)
INSERT INTO seats (seat_id, event_id, row_number, seat_number, status) VALUES
('55555555-5555-5555-5555-555555555101', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'A', 1, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555102', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'A', 2, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555103', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'A', 3, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555104', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'A', 4, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555105', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'A', 5, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555106', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'B', 1, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555107', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'B', 2, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555108', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'B', 3, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555109', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'B', 4, 'AVAILABLE'),
('55555555-5555-5555-5555-555555555110', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'B', 5, 'AVAILABLE')
ON CONFLICT (seat_id) DO NOTHING;
