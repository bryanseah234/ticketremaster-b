from app import create_app, db
from models import Venue


VENUES = [
    {
        'venueId': 'ven_001',
        'name': 'Esplanade Concert Hall',
        'capacity': 40,
        'address': '1 Esplanade Dr, Singapore',
        'postalCode': '038981',
        'coordinates': '1.2897,103.8555',
        'isActive': True,
    },
    {
        'venueId': 'ven_002',
        'name': 'Singapore Indoor Stadium',
        'capacity': 50,
        'address': '2 Stadium Walk, Singapore',
        'postalCode': '397691',
        'coordinates': '1.3006,103.8745',
        'isActive': True,
    },
    {
        'venueId': 'ven_003',
        'name': 'Capitol Theatre',
        'capacity': 60,
        'address': '17 Stamford Rd, Singapore',
        'postalCode': '178907',
        'coordinates': '1.2935,103.8519',
        'isActive': True,
    },
    {
        'venueId': 'ven_004',
        'name': 'Sands Theatre',
        'capacity': 70,
        'address': '10 Bayfront Ave, Singapore',
        'postalCode': '018956',
        'coordinates': '1.2834,103.8607',
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
