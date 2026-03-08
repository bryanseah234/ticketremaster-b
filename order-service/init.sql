-- Order Service — orders_db schema

-- Enum Types
DO $$ BEGIN
    CREATE TYPE order_status AS ENUM ('PENDING', 'CONFIRMED', 'FAILED', 'REFUNDED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE transfer_initiator AS ENUM ('SELLER', 'BUYER');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE transfer_status AS ENUM ('INITIATED', 'PENDING_OTP', 'COMPLETED', 'DISPUTED', 'REVERSED', 'FAILED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE marketplace_listing_status AS ENUM ('ACTIVE', 'PENDING_TRANSFER', 'COMPLETED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Orders Table
CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL, -- References users_db (logical FK)
    seat_id UUID NOT NULL, -- References seats_db (logical FK)
    event_id UUID NOT NULL, -- Denormalized for query convenience
    status order_status NOT NULL DEFAULT 'PENDING',
    credits_charged NUMERIC(10, 2) NOT NULL,
    verification_sid TEXT, -- For high-risk purchase OTP
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP
);

-- Transfers Table
CREATE TABLE IF NOT EXISTS transfers (
    transfer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seat_id UUID NOT NULL,
    seller_user_id UUID NOT NULL,
    buyer_user_id UUID NOT NULL,
    initiated_by transfer_initiator NOT NULL,
    status transfer_status NOT NULL DEFAULT 'INITIATED',
    seller_otp_verified BOOLEAN DEFAULT FALSE,
    buyer_otp_verified BOOLEAN DEFAULT FALSE,
    seller_verification_sid TEXT,
    buyer_verification_sid TEXT,
    credits_amount NUMERIC(10, 2),
    dispute_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_seat_id ON orders(seat_id);
CREATE INDEX IF NOT EXISTS idx_transfers_seat_id ON transfers(seat_id);
CREATE INDEX IF NOT EXISTS idx_transfers_seller_user_id ON transfers(seller_user_id);
CREATE INDEX IF NOT EXISTS idx_transfers_buyer_user_id ON transfers(buyer_user_id);

-- Partial Unique Index (Concurrency Control)
-- Prevents multiple pending transfers for samet seat
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_transfer_per_seat 
ON transfers (seat_id) 
WHERE status IN ('INITIATED', 'PENDING_OTP');

-- Marketplace Listings Table
CREATE TABLE IF NOT EXISTS marketplace_listings (
    listing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seat_id UUID NOT NULL,
    seller_user_id UUID NOT NULL,
    buyer_user_id UUID,
    escrow_transaction_id UUID,
    asking_price NUMERIC(10, 2) NOT NULL,
    status marketplace_listing_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_marketplace_listings_seat_id ON marketplace_listings(seat_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_seller_id ON marketplace_listings(seller_user_id);

-- Prevents multiple pending listings for same seat
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_listing_per_seat 
ON marketplace_listings (seat_id) 
WHERE status IN ('ACTIVE', 'PENDING_TRANSFER');
