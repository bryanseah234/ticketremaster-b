from app import create_app, db
from models import Venue


VENUES = [
    {
        'venueId': 'ven_001',
        'name': 'Esplanade Concert Hall',
        'capacity': 1600,
        'address': '1 Esplanade Drive, Singapore',
        'postalCode': '038981',
        'coordinates': '1.2897,103.8555',
        'isActive': True,
    },
    {
        'venueId': 'ven_002',
        'name': 'Singapore Indoor Stadium',
        'capacity': 12000,
        'address': '2 Stadium Walk, Singapore',
        'postalCode': '397691',
        'coordinates': '1.3006,103.8745',
        'isActive': True,
    },
    {
        'venueId': 'ven_003',
        'name': 'Capitol Theatre',
        'capacity': 800,
        'address': '17 Stamford Road, Singapore',
        'postalCode': '178907',
        'coordinates': '1.2935,103.8519',
        'isActive': True,
    },
    {
        'venueId': 'ven_004',
        'name': 'Sands Theatre',
        'capacity': 1680,
        'address': '10 Bayfront Avenue, B1-69/70 The Shoppes at Marina Bay Sands, Singapore',
        'postalCode': '018971',
        'coordinates': '1.2834,103.8607',
        'isActive': True,
    },
    {
        'venueId': 'ven_005',
        'name': 'National Stadium',
        'capacity': 55000,
        'address': '1 Stadium Drive, Singapore',
        'postalCode': '397629',
        'coordinates': '1.3044,103.8743',
        'isActive': True,
    },
    {
        'venueId': 'ven_006',
        'name': 'Gardens by the Bay',
        'capacity': 10000,
        'address': '18 Marina Gardens Drive, Singapore',
        'postalCode': '018953',
        'coordinates': '1.2816,103.8636',
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
