import math

from app import create_app, db
from models import Seat


def iter_rows_a_to_z():
    for char_code in range(ord('A'), ord('Z') + 1):
        yield chr(char_code)


VENUE_CAPACITIES = {
    'ven_001': 1800,
    'ven_002': 12000,
}


def seed_venue(venue_id, capacity):
    seats_per_row = math.ceil(capacity / 26)
    existing_seat_numbers = {
        seat_number
        for (seat_number,) in db.session.query(Seat.seatNumber)
        .filter_by(venueId=venue_id)
        .all()
    }

    to_create = []
    created_count = 0
    for row in iter_rows_a_to_z():
        for seat_index in range(1, seats_per_row + 1):
            if created_count >= capacity:
                break
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
            created_count += 1

        if created_count >= capacity:
            break

    if to_create:
        db.session.bulk_save_objects(to_create)

    return len(to_create)


app = create_app()

with app.app_context():
    created_venue_1 = seed_venue('ven_001', VENUE_CAPACITIES['ven_001'])
    created_venue_2 = seed_venue('ven_002', VENUE_CAPACITIES['ven_002'])

    db.session.commit()
    print(
        'Seed complete. '
        f'Created {created_venue_1} seat(s) for ven_001 and {created_venue_2} seat(s) for ven_002.'
    )
