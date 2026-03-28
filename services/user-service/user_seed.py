import bcrypt
from app import create_app, db
from models import User


def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


TEST_USERS = [
    {
        'email': 'admin@ticketremaster.local',
        'password': 'admin123',
        'phoneNumber': '+6500000001',
        'role': 'admin',
        'isFlagged': False,
    },
    {
        'email': 'staff@ticketremaster.local',
        'password': 'staff123',
        'phoneNumber': '+6500000002',
        'role': 'staff',
        'isFlagged': False,
    },
    {
        'email': 'user@ticketremaster.local',
        'password': 'user123',
        'phoneNumber': '+6500000003',
        'role': 'user',
        'isFlagged': False,
    },
]


app = create_app()

with app.app_context():
    created = 0
    for user_data in TEST_USERS:
        existing = User.query.filter_by(email=user_data['email']).first()
        if existing:
            print(f"Skipping {user_data['email']} - already exists")
            continue

        # Hash the password and generate a new salt
        password_plain = user_data.pop('password')
        user_data['password'] = hash_password(password_plain)
        user_data['salt'] = bcrypt.gensalt().decode()  # Store salt separately for reference
        
        db.session.add(User(**user_data))
        created += 1
        print(f"Created {user_data['email']} ({user_data['role']})")

    db.session.commit()
    print(f'\nSeed complete. Created {created} user(s).')