from app import create_app, db
from models import Seat


def iter_rows_a_to_z():
    for char_code in range(ord('A'), ord('Z') + 1):
        yield chr(char_code)


def seed_venue(venue_id, max_seat_per_row):
    existing_seat_numbers = {
        seat_number
        for (seat_number,) in db.session.query(Seat.seatNumber)
        .filter_by(venueId=venue_id)
        .all()
    }

    to_create = []
    for row in iter_rows_a_to_z():
        for seat_index in range(1, max_seat_per_row + 1):
            seat_number = f'{row}{seat_index}'
            if seat_number in existing_seat_numbers:
                continue
            to_create.append(
                Seat(
                    venueId=venue_id,
                    seatNumber=seat_number,
                    rowNumber=row,
                )
            )

    if to_create:
        db.session.bulk_save_objects(to_create)

    return len(to_create)


app = create_app()

with app.app_context():
    # ven_001 target capacity is 1800; this deterministic layout seeds 26 x 69 = 1794 seats.
    created_venue_1 = seed_venue('ven_001', 69)

    # ven_002 target capacity is 12000; for demo/local development we seed 26 x 20 = 520 seats.
    # Full seeding can scale by increasing per-row seats and adding multi-letter row labels.
    created_venue_2 = seed_venue('ven_002', 20)

    db.session.commit()
    print(
        'Seed complete. '
        f'Created {created_venue_1} seat(s) for ven_001 and {created_venue_2} seat(s) for ven_002.'
    )
