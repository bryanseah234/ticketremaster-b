from app import create_app, db
from models import Venue


VENUES = [
    {
        'venueId': 'ven_001',
        'name': 'Esplanade Concert Hall',
        'capacity': 1800,
        'address': '1 Esplanade Dr',
        'postalCode': '038981',
        'coordinates': '1.2897,103.8555',
        'isActive': True,
    },
    {
        'venueId': 'ven_002',
        'name': 'Singapore Indoor Stadium',
        'capacity': 12000,
        'address': '2 Stadium Walk',
        'postalCode': '397691',
        'coordinates': '1.3006,103.8745',
        'isActive': True,
    },
]


app = create_app()

with app.app_context():
    created = 0
    for venue_data in VENUES:
        existing = db.session.get(Venue, venue_data['venueId'])
        if existing:
            continue

        db.session.add(Venue(**venue_data))
        created += 1

    db.session.commit()
    print(f'Seed complete. Created {created} venue(s).')
