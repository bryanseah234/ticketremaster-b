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
