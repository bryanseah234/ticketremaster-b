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
        'image': 'https://picsum.photos/seed/eras-tour/800/450',
        'price': 248.00,
    },
    {
        'eventId': 'evt_002',
        'venueId': 'ven_001',
        'name': 'SSO Gala: Beethoven\'s 9th',
        'date': datetime(2026, 7, 20, 20, 0),
        'description': 'The Singapore Symphony Orchestra performs Beethoven\'s masterpiece.',
        'type': 'classical',
        'image': 'https://picsum.photos/seed/sso-beethoven/800/450',
        'price': 85.00,
    },
    {
        'eventId': 'evt_003',
        'venueId': 'ven_001',
        'name': 'DAY6 10th Anniversary Tour <The DECADE>',
        'date': datetime(2026, 8, 18, 18, 0),
        'description': 'K-pop rock band DAY6 celebrates their 10th anniversary with an electrifying performance.',
        'type': 'concert',
        'image': 'https://picsum.photos/seed/day6-decade/800/450',
        'price': 158.00,
    },
    {
        'eventId': 'evt_004',
        'venueId': 'ven_002',
        'name': 'Harry Styles: Together, Together',
        'date': datetime(2026, 8, 26, 20, 0),
        'description': 'International superstar Harry Styles returns as part of his Together, Together world tour.',
        'type': 'concert',
        'image': 'https://picsum.photos/seed/harry-styles/800/450',
        'price': 150.00,
    },
    {
        'eventId': 'evt_005',
        'venueId': 'ven_002',
        'name': 'Coldplay: Music of the Spheres',
        'date': datetime(2026, 9, 5, 20, 0),
        'description': 'Coldplay brings their spectacular Music of the Spheres World Tour to Singapore.',
        'type': 'concert',
        'image': 'https://picsum.photos/seed/coldplay-spheres/800/450',
        'price': 188.00,
    },
    {
        'eventId': 'evt_006',
        'venueId': 'ven_002',
        'name': 'Singapore Jazz Festival 2026',
        'date': datetime(2026, 5, 10, 18, 0),
        'description': 'Three nights of world-class jazz featuring international and local artists.',
        'type': 'festival',
        'image': 'https://picsum.photos/seed/sg-jazz-2026/800/450',
        'price': 75.00,
    },
    {
        'eventId': 'evt_007',
        'venueId': 'ven_003',
        'name': 'A.R. Rahman Live in Concert',
        'date': datetime(2026, 10, 25, 19, 0),
        'description': 'Legendary composer A.R. Rahman performs his greatest hits live.',
        'type': 'concert',
        'image': 'https://picsum.photos/seed/ar-rahman/800/450',
        'price': 95.00,
    },
    {
        'eventId': 'evt_008',
        'venueId': 'ven_003',
        'name': 'Hans Zimmer Live',
        'date': datetime(2026, 11, 21, 20, 0),
        'description': 'Experience the epic film scores of Hans Zimmer performed live by a full orchestra.',
        'type': 'classical',
        'image': 'https://picsum.photos/seed/hans-zimmer/800/450',
        'price': 88.00,
    },
    {
        'eventId': 'evt_009',
        'venueId': 'ven_004',
        'name': 'Guns N\' Roses - World Tour 2026',
        'date': datetime(2026, 7, 1, 20, 0),
        'description': 'The legendary rock band Guns N\' Roses brings their explosive World Tour to Singapore.',
        'type': 'concert',
        'image': 'https://picsum.photos/seed/gnr-2026/800/450',
        'price': 125.00,
    },
    {
        'eventId': 'evt_010',
        'venueId': 'ven_004',
        'name': 'Mountbatten Festival of Music 2026',
        'date': datetime(2026, 9, 30, 19, 30),
        'description': 'The Massed Bands showcase their incredible musicianship and military pageantry.',
        'type': 'classical',
        'image': 'https://picsum.photos/seed/mountbatten-2026/800/450',
        'price': 65.00,
    },
    # --- Sports ---
    {
        'eventId': 'evt_011',
        'venueId': 'ven_005',
        'name': 'HSBC SVNS Singapore 2026',
        'date': datetime(2026, 10, 31, 10, 0),
        'description': 'World-class rugby sevens action returns to the National Stadium with teams from across the globe competing in the HSBC SVNS series.',
        'type': 'sports',
        'image': 'https://picsum.photos/seed/hsbc-svns-2026/800/450',
        'price': 59.00,
    },
    {
        'eventId': 'evt_012',
        'venueId': 'ven_005',
        'name': 'Singapore Grand Prix 2026',
        'date': datetime(2026, 9, 20, 20, 0),
        'description': 'The Formula 1 Singapore Airlines Singapore Grand Prix returns for another thrilling night race on the Marina Bay Street Circuit.',
        'type': 'sports',
        'image': 'https://picsum.photos/seed/f1-sg-2026/800/450',
        'price': 198.00,
    },
    # --- Theatre ---
    {
        'eventId': 'evt_013',
        'venueId': 'ven_001',
        'name': 'Legally Blonde – The Musical',
        'date': datetime(2026, 7, 29, 19, 30),
        'description': 'Singapore Repertory Theatre presents the West End and Broadway smash hit, led by Singaporean star Nathania Ong as Elle Woods.',
        'type': 'theatre',
        'image': 'https://picsum.photos/seed/legally-blonde-sg/800/450',
        'price': 98.00,
    },
    {
        'eventId': 'evt_014',
        'venueId': 'ven_003',
        'name': 'CATS – The Musical',
        'date': datetime(2026, 11, 6, 19, 30),
        'description': 'Andrew Lloyd Webber\'s iconic musical phenomenon comes to Singapore, featuring beloved songs and mesmerising choreography.',
        'type': 'theatre',
        'image': 'https://picsum.photos/seed/cats-musical-sg/800/450',
        'price': 115.00,
    },
    # --- Festival ---
    {
        'eventId': 'evt_015',
        'venueId': 'ven_006',
        'name': 'Singapore Garden Festival 2026',
        'date': datetime(2026, 7, 4, 9, 0),
        'description': 'The 10th edition of Singapore\'s premier international garden and flower show returns to Gardens by the Bay, featuring world-class floral displays and landscape installations.',
        'type': 'festival',
        'image': 'https://picsum.photos/seed/sg-garden-fest-2026/800/450',
        'price': 35.00,
    },
    {
        'eventId': 'evt_016',
        'venueId': 'ven_006',
        'name': 'i Light Singapore 2026',
        'date': datetime(2026, 6, 6, 19, 0),
        'description': 'Asia\'s leading sustainable light art festival illuminates the Marina Bay waterfront with stunning large-scale light art installations from local and international artists.',
        'type': 'festival',
        'image': 'https://picsum.photos/seed/ilight-sg-2026/800/450',
        'price': 25.00,
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
