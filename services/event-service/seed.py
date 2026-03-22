from datetime import datetime
from app import create_app, db
from models import Event

# Seed at least 2 events pointing to ven_001 and ven_002
SEED_EVENTS = [
    {
        "eventId": "evt_001",
        "venueId": "ven_001",
        "name": "Taylor Swift | The Eras Tour",
        "date": datetime(2025, 6, 15, 19, 30),
        "description": "Experience the magic of Taylor Swift live in Singapore.",
        "type": "concert",
        "image": "https://example.com/eras-tour.jpg",
        "price": 248.00,
    },
    {
        "eventId": "evt_002",
        "venueId": "ven_002",
        "name": "SSO Gala: Beethoven's 9th",
        "date": datetime(2025, 7, 20, 20, 0),
        "description": "The Singapore Symphony Orchestra performs Beethoven's masterpiece.",
        "type": "orchestra",
        "image": "https://example.com/sso-gala.jpg",
        "price": 85.00,
    },
    {
        "eventId": "evt_003",
        "venueId": "ven_002",
        "name": "DAY6 10th Anniversary Tour <The DECADE>",
        "date": datetime(2026, 4, 18, 18, 0),
        "description": "K-pop rock band DAY6 celebrates their 10th anniversary with an electrifying performance in Singapore.",
        "type": "concert",
        "image": "https://example.com/day6-decade.jpg",
        "price": 158.00,
    },
    {
        "eventId": "evt_004",
        "venueId": "ven_004",
        "name": "Harry Styles: Together, Together",
        "date": datetime(2026, 8, 26, 20, 0),
        "description": "International superstar Harry Styles returns to The Garden as part of his Together, Together world tour.",
        "type": "concert",
        "image": "https://example.com/harry-styles-msg.jpg",
        "price": 150.00,
    },
    {
        "eventId": "evt_005",
        "venueId": "ven_004",
        "name": "New York Knicks vs. Golden State Warriors",
        "date": datetime(2026, 3, 15, 19, 30),
        "description": "The New York Knicks take on the Golden State Warriors in a highly anticipated regular-season NBA matchup.",
        "type": "sports",
        "image": "https://example.com/knicks-warriors.jpg",
        "price": 120.00,
    },
    {
        "eventId": "evt_006",
        "venueId": "ven_003",
        "name": "Mountbatten Festival of Music 2026",
        "date": datetime(2026, 3, 20, 19, 30),
        "description": "The Massed Bands of His Majesty's Royal Marines showcase their incredible musicianship and military pageantry.",
        "type": "classical",
        "image": "https://example.com/mountbatten-festival.jpg",
        "price": 65.00,
    },
    {
        "eventId": "evt_007",
        "venueId": "ven_003",
        "name": "A.R. Rahman Live in Concert",
        "date": datetime(2026, 4, 25, 19, 0),
        "description": "Legendary composer A.R. Rahman performs live with the Royal Philharmonic Orchestra.",
        "type": "concert",
        "image": "https://example.com/ar-rahman-rah.jpg",
        "price": 95.00,
    },
    {
        "eventId": "evt_008",
        "venueId": "ven_007",
        "name": "Hans Zimmer Live",
        "date": datetime(2026, 3, 21, 20, 0),
        "description": "Experience the epic film scores of Hans Zimmer performed live by an orchestra in Paris.",
        "type": "concert",
        "image": "https://example.com/hans-zimmer-paris.jpg",
        "price": 88.75,
    },
    {
        "eventId": "evt_009",
        "venueId": "ven_007",
        "name": "Guns N' Roses - World Tour 2026",
        "date": datetime(2026, 7, 1, 20, 0),
        "description": "The legendary rock band Guns N' Roses brings their explosive World Tour to the Accor Arena.",
        "type": "concert",
        "image": "https://example.com/gnr-paris.jpg",
        "price": 125.00,
    }
]

app = create_app()

with app.app_context():
    created = 0
    for event_data in SEED_EVENTS:
        existing = Event.query.filter_by(eventId=event_data["eventId"]).first()
        if existing:
            continue

        db.session.add(Event(**event_data))
        created += 1

    db.session.commit()
    print(f"Seed complete. Created {created} event(s).")
