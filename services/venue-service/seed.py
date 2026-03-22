from app import create_app, db
from models import Venue


VENUES = [
    {
        'venueId': 'ven_001',
        'name': 'Esplanade Concert Hall',
        'capacity': 1800,
        'address': '1 Esplanade Dr, Singapore',
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
        'name': 'Royal Albert Hall',
        'capacity': 5272,
        'address': 'Kensington Gore, South Kensington, London, UK',
        'postalCode': 'SW7 2AP',
        'coordinates': '51.5009,-0.1774',
        'isActive': True,
    },
    {
        'venueId': 'ven_004',
        'name': 'Madison Square Garden',
        'capacity': 19500,
        'address': '4 Pennsylvania Plaza, New York, NY, USA',
        'postalCode': '10001',
        'coordinates': '40.7505,-73.9934',
        'isActive': True,
    },
    {
        'venueId': 'ven_005',
        'name': 'Sydney Opera House (Concert Hall)',
        'capacity': 2679,
        'address': 'Bennelong Point, Sydney NSW, Australia',
        'postalCode': '2000',
        'coordinates': '-33.8568,151.2153',
        'isActive': True,
    },
    {
        'venueId': 'ven_006',
        'name': 'Nippon Budokan',
        'capacity': 14471,
        'address': '2-3 Kitanomarukoen, Chiyoda City, Tokyo, Japan',
        'postalCode': '102-8321',
        'coordinates': '35.6933,139.7500',
        'isActive': True,
    },
    {
        'venueId': 'ven_007',
        'name': 'Accor Arena',
        'capacity': 20300,
        'address': '8 Bd de Bercy, Paris, France',
        'postalCode': '75012',
        'coordinates': '48.8386,2.3785',
        'isActive': True,
    },
    {
        'venueId': 'ven_008',
        'name': 'Theatro Municipal do Rio de Janeiro',
        'capacity': 2361,
        'address': 'Praça Floriano, S/N - Centro, Rio de Janeiro - RJ, Brazil',
        'postalCode': '20031-050',
        'coordinates': '-22.9089,-43.1760',
        'isActive': True,
    },
    {
        'venueId': 'ven_009',
        'name': 'SunBet Arena at Time Square',
        'capacity': 8500,
        'address': '209 Aramist Ave, Waterkloof Glen, Pretoria, South Africa',
        'postalCode': '0010',
        'coordinates': '-25.7877,28.2806',
        'isActive': True,
    },
    {
        'venueId': 'ven_010',
        'name': 'Mercedes-Benz Arena',
        'capacity': 18000,
        'address': '1200 Expo Ave, Pudong, Shanghai, China',
        'postalCode': '200126',
        'coordinates': '31.1911,121.4878',
        'isActive': True,
    }
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
