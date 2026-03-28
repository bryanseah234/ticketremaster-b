from datetime import datetime

from app import create_app, db
from models import Event


SEED_EVENTS = [
    {
        'eventId': 'evt_001',
        'venueId': 'ven_001',
        'name': 'Taylor Swift | The Eras Tour',
        'date': datetime(2026, 6, 15, 19, 30),
        'description': 'Experience the magic of Taylor Swift live in Singapore.',
        'type': 'concert',
        'image': 'https://example.com/eras-tour.jpg',
        'price': 248.00,
    },
    {
        'eventId': 'evt_002',
        'venueId': 'ven_001',
        'name': 'SSO Gala: Beethoven\'s 9th',
        'date': datetime(2026, 7, 20, 20, 0),
        'description': 'The Singapore Symphony Orchestra performs Beethoven\'s masterpiece.',
        'type': 'orchestra',
        'image': 'https://example.com/sso-gala.jpg',
        'price': 85.00,
    },
    {
        'eventId': 'evt_003',
        'venueId': 'ven_001',
        'name': 'DAY6 10th Anniversary Tour <The DECADE>',
        'date': datetime(2026, 8, 18, 18, 0),
        'description': 'K-pop rock band DAY6 celebrates their 10th anniversary with an electrifying performance.',
        'type': 'concert',
        'image': 'https://example.com/day6-decade.jpg',
        'price': 158.00,
    },
    {
        'eventId': 'evt_004',
        'venueId': 'ven_002',
        'name': 'Harry Styles: Together, Together',
        'date': datetime(2026, 8, 26, 20, 0),
        'description': 'International superstar Harry Styles returns as part of his Together, Together world tour.',
        'type': 'concert',
        'image': 'https://example.com/harry-styles.jpg',
        'price': 150.00,
    },
    {
        'eventId': 'evt_005',
        'venueId': 'ven_002',
        'name': 'Coldplay: Music of the Spheres',
        'date': datetime(2026, 9, 5, 20, 0),
        'description': 'Coldplay brings their spectacular Music of the Spheres World Tour to Singapore.',
        'type': 'concert',
        'image': 'https://example.com/coldplay.jpg',
        'price': 188.00,
    },
    {
        'eventId': 'evt_006',
        'venueId': 'ven_002',
        'name': 'Singapore Jazz Festival 2026',
        'date': datetime(2026, 5, 10, 18, 0),
        'description': 'Three nights of world-class jazz featuring international and local artists.',
        'type': 'jazz',
        'image': 'https://example.com/sg-jazz-fest.jpg',
        'price': 75.00,
    },
    {
        'eventId': 'evt_007',
        'venueId': 'ven_003',
        'name': 'A.R. Rahman Live in Concert',
        'date': datetime(2026, 10, 25, 19, 0),
        'description': 'Legendary composer A.R. Rahman performs his greatest hits live.',
        'type': 'concert',
        'image': 'https://example.com/ar-rahman.jpg',
        'price': 95.00,
    },
    {
        'eventId': 'evt_008',
        'venueId': 'ven_003',
        'name': 'Hans Zimmer Live',
        'date': datetime(2026, 11, 21, 20, 0),
        'description': 'Experience the epic film scores of Hans Zimmer performed live by a full orchestra.',
        'type': 'orchestra',
        'image': 'https://example.com/hans-zimmer.jpg',
        'price': 88.00,
    },
    {
        'eventId': 'evt_009',
        'venueId': 'ven_004',
        'name': 'Guns N\' Roses - World Tour 2026',
        'date': datetime(2026, 7, 1, 20, 0),
        'description': 'The legendary rock band Guns N\' Roses brings their explosive World Tour to Singapore.',
        'type': 'concert',
        'image': 'https://example.com/gnr.jpg',
        'price': 125.00,
    },
    {
        'eventId': 'evt_010',
        'venueId': 'ven_004',
        'name': 'Mountbatten Festival of Music 2026',
        'date': datetime(2026, 9, 30, 19, 30),
        'description': 'The Massed Bands showcase their incredible musicianship and military pageantry.',
        'type': 'classical',
        'image': 'https://example.com/mountbatten.jpg',
        'price': 65.00,
    },
]


app = create_app()

with app.app_context():
    created = 0
    for event_data in SEED_EVENTS:
        existing = Event.query.filter_by(eventId=event_data['eventId']).first()
        if existing:
            continue

        db.session.add(Event(**event_data))
        created += 1

    db.session.commit()
    print(f'Seed complete. Created {created} event(s).')
