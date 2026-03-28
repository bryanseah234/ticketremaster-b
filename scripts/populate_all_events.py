"""
Seed script: inserts 10 events, 100 seats per venue (10 rows x 10 seats),
and seat inventory records for each event.

Run from the repo root (requires Docker services to be running):
    python scripts/populate_all_events.py

DB ports (mapped in docker-compose.yml):
    event-service-db          -> 5432 (mapped to host varies, run via psycopg2 direct)
    seat-service-db           -> host port check docker-compose
    seat-inventory-service-db -> host port check docker-compose

Or run inside the containers:
    docker cp scripts/populate_all_events.py ticketremaster-event-service-1:/app/
    docker exec ticketremaster-event-service-1 python populate_all_events.py
"""
import uuid
from datetime import datetime

import psycopg2

ROWS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
SEATS_PER_ROW = 10
NOW = datetime.utcnow()

# ── Event definitions ─────────────────────────────────────────────────────────
EVENTS = [
    {
        "eventId":     "evt-001",
        "venueId":     "ven_002",
        "name":        "Neon Skyline Festival",
        "description": "An electrifying night of EDM and light shows.",
        "type":        "festival",
        "image":       "https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?q=80&w=1400",
        "price":       120.0,
        "date":        "2026-04-13 20:00:00",
    },
    {
        "eventId":     "evt-002",
        "venueId":     "ven_001",
        "name":        "Global Bass Arena",
        "description": "World-class DJs bring the bass to Singapore Indoor Stadium.",
        "type":        "concert",
        "image":       "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?q=80&w=1400",
        "price":       180.0,
        "date":        "2026-06-01 19:00:00",
    },
    {
        "eventId":     "evt-003",
        "venueId":     "ven_004",
        "name":        "Symphony Under the Stars",
        "description": "A classical evening with the Singapore Symphony Orchestra.",
        "type":        "classical",
        "image":       "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?q=80&w=1400",
        "price":       95.0,
        "date":        "2026-05-10 19:30:00",
    },
    {
        "eventId":     "evt-004",
        "venueId":     "ven_007",
        "name":        "Fort Canning Indie Fest",
        "description": "Indie rock and folk acts across three stages.",
        "type":        "festival",
        "image":       "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?q=80&w=1400",
        "price":       85.0,
        "date":        "2026-04-30 18:00:00",
    },
    {
        "eventId":     "evt-005",
        "venueId":     "ven_003",
        "name":        "Phantom of the Opera",
        "description": "The legendary musical returns to Singapore.",
        "type":        "theatre",
        "image":       "https://images.unsplash.com/photo-1520527057852-44c0e5c43dc4?q=80&w=1400",
        "price":       220.0,
        "date":        "2026-05-22 19:00:00",
    },
    {
        "eventId":     "evt-006",
        "venueId":     "ven_009",
        "name":        "Sentosa Sunset Rave",
        "description": "Beach party rave at Palawan with international DJs.",
        "type":        "concert",
        "image":       "https://images.unsplash.com/photo-1493225255756-d9584f8606e9?q=80&w=1400",
        "price":       150.0,
        "date":        "2026-07-04 16:00:00",
    },
    {
        "eventId":     "evt-007",
        "venueId":     "ven_005",
        "name":        "Jazz at Capitol",
        "description": "Intimate jazz sessions in the restored Capitol Theatre.",
        "type":        "concert",
        "image":       "https://images.unsplash.com/photo-1511192336575-5a79af67a629?q=80&w=1400",
        "price":       110.0,
        "date":        "2026-05-15 19:30:00",
    },
    {
        "eventId":     "evt-008",
        "venueId":     "ven_008",
        "name":        "Red Bull Music Weekend",
        "description": "Hip-hop and urban music festival at Kallang.",
        "type":        "festival",
        "image":       "https://images.unsplash.com/photo-1464375117522-1311d6a5b81f?q=80&w=1400",
        "price":       135.0,
        "date":        "2026-06-20 14:00:00",
    },
    {
        "eventId":     "evt-009",
        "venueId":     "ven_010",
        "name":        "K-Wave Star Concert",
        "description": "Top K-pop acts perform live at Star Theatre.",
        "type":        "concert",
        "image":       "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?q=80&w=1400",
        "price":       300.0,
        "date":        "2026-07-12 18:00:00",
    },
    {
        "eventId":     "evt-010",
        "venueId":     "ven_006",
        "name":        "Shakespeare in Victoria",
        "description": "A Midsummer Night Dream at the historic Victoria Theatre.",
        "type":        "theatre",
        "image":       "https://images.unsplash.com/photo-1514525253361-bee8d48800d5?q=80&w=1400",
        "price":       90.0,
        "date":        "2026-04-25 19:00:00",
    },
]

# ── DB connections (uses host-mapped ports from docker-compose.yml) ───────────
event_conn = psycopg2.connect(host="event-service-db", port=5432, dbname="event_service",
                               user="ticketremaster", password="event_dev_pass")
seat_conn  = psycopg2.connect(host="seat-service-db", port=5432, dbname="seat_service",
                               user="ticketremaster", password="change_me")
inv_conn   = psycopg2.connect(host="seat-inventory-service-db", port=5432, dbname="seat_inventory_service",
                               user="ticketremaster", password="inventory_dev_pass")

event_cur = event_conn.cursor()
seat_cur  = seat_conn.cursor()
inv_cur   = inv_conn.cursor()

# ── 1. Insert events ──────────────────────────────────────────────────────────
for ev in EVENTS:
    event_cur.execute(
        '''INSERT INTO events ("eventId", "venueId", name, description, type, image, price, date, "createdAt")
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT ("eventId") DO NOTHING''',
        (ev["eventId"], ev["venueId"], ev["name"], ev["description"],
         ev["type"], ev["image"], ev["price"], ev["date"], NOW)
    )
event_conn.commit()
print(f"Inserted {len(EVENTS)} events.")

# ── 2. Insert seats (100 per venue, 10 rows x 10 seats) ───────────────────────
venue_seats = {}  # venueId -> list of seatIds

all_venues = list({ev["venueId"] for ev in EVENTS})
for venue_id in all_venues:
    seat_cur.execute('SELECT "seatId" FROM seats WHERE "venueId" = %s', (venue_id,))
    existing = [r[0] for r in seat_cur.fetchall()]
    if existing:
        venue_seats[venue_id] = existing
        print(f"  {venue_id}: {len(existing)} seats already exist, skipping.")
        continue

    seat_ids = []
    for row_letter in ROWS:
        for seat_num in range(1, SEATS_PER_ROW + 1):
            seat_id = str(uuid.uuid4())
            seat_cur.execute(
                '''INSERT INTO seats ("seatId", "venueId", "seatNumber", "rowNumber", "createdAt")
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING''',
                (seat_id, venue_id, f"{row_letter}{seat_num}", row_letter, NOW)
            )
            seat_ids.append(seat_id)
    seat_conn.commit()

    seat_cur.execute('SELECT "seatId" FROM seats WHERE "venueId" = %s', (venue_id,))
    venue_seats[venue_id] = [r[0] for r in seat_cur.fetchall()]
    print(f"  {venue_id}: created {len(venue_seats[venue_id])} seats.")

# ── 3. Insert seat inventory ──────────────────────────────────────────────────
for ev in EVENTS:
    seat_ids = venue_seats.get(ev["venueId"], [])
    if not seat_ids:
        print(f"  {ev['eventId']}: no seats found for {ev['venueId']}, skipping.")
        continue

    inserted = 0
    for seat_id in seat_ids:
        inv_cur.execute(
            '''INSERT INTO seat_inventory
               ("inventoryId", "eventId", "seatId", status, "createdAt", "updatedAt")
               VALUES (%s, %s, %s, 'available', %s, %s)
               ON CONFLICT ("eventId", "seatId") DO NOTHING''',
            (str(uuid.uuid4()), ev["eventId"], seat_id, NOW, NOW)
        )
        inserted += 1
    inv_conn.commit()
    print(f"  {ev['eventId']} ({ev['name']}): {inserted} inventory records.")

event_conn.close()
seat_conn.close()
inv_conn.close()
print("Done!")
