-- Event Service — events_db schema

-- Venues Table
CREATE TABLE IF NOT EXISTS venues (
    venue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    address TEXT NOT NULL,
    total_halls INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Events Table
CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    venue_id UUID REFERENCES venues(venue_id),
    hall_id VARCHAR(20) NOT NULL,
    event_date TIMESTAMP NOT NULL,
    total_seats INT NOT NULL,
    pricing_tiers JSONB NOT NULL,
    seat_selection_mode VARCHAR(20) NOT NULL DEFAULT 'SEATMAP',
    seat_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════════
-- Seed Data — See SEED_DATA.md at project root for full reference
-- ═══════════════════════════════════════════════════════════════
-- Venue UUID: a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1
-- Event UUID: e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1
INSERT INTO venues (venue_id, name, address, total_halls) VALUES
('a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1', 'Singapore Indoor Stadium', '2 Stadium Walk, Singapore 397691', 1)
ON CONFLICT (venue_id) DO NOTHING;

-- 1 Event: Taylor Swift Eras Tour
INSERT INTO events (event_id, name, venue_id, hall_id, event_date, total_seats, pricing_tiers, seat_selection_mode, seat_config) VALUES
('e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1', 'Taylor Swift: The Eras Tour', 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1', 'HALL-A', '2026-03-02 19:00:00', 10000, '{"CAT1": 350, "CAT2": 250, "CAT3": 180}', 'SEATMAP', '{"category_rows":{"CAT1":["1","2"],"CAT2":["3","4"],"CAT3":["5","6"]}}')
ON CONFLICT (event_id) DO NOTHING;
