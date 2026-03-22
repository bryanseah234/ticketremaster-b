from app import create_app, db
from models import User


ADMIN_USERS = [
    {
        'email': 'admin1@ticketremaster.local',
        'password': 'seeded-admin-password-hash-1',
        'salt': 'seeded-admin-salt-1',
        'phoneNumber': '+6500000001',
        'role': 'admin',
        'isFlagged': False,
    },
    {
        'email': 'admin2@ticketremaster.local',
        'password': 'seeded-admin-password-hash-2',
        'salt': 'seeded-admin-salt-2',
        'phoneNumber': '+6500000002',
        'role': 'admin',
        'isFlagged': False,
    },
]


app = create_app()

with app.app_context():
    created = 0
    for admin_data in ADMIN_USERS:
        existing = User.query.filter_by(email=admin_data['email']).first()
        if existing:
            continue

        db.session.add(User(**admin_data))
        created += 1

    db.session.commit()
    print(f'Seed complete. Created {created} admin user(s).')
