import os

import requests

from app import create_app, db
from models import SeatInventory


def fetch_events(event_service_url):
    response = requests.get(f'{event_service_url}/events', timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload.get('events', [])


def fetch_seats_for_venue(seat_service_url, venue_id):
    response = requests.get(f'{seat_service_url}/seats/venue/{venue_id}', timeout=10)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload.get('seats', [])
    return payload


def resolve_seat_id(seat):
    return seat.get('seatId') or seat.get('seat_id') or seat.get('id')


app = create_app()

event_service_url = os.getenv('EVENT_SERVICE_URL', 'http://event-service:5000').rstrip('/')
seat_service_url = os.getenv('SEAT_SERVICE_URL', 'http://seat-service:5000').rstrip('/')

events = fetch_events(event_service_url)

with app.app_context():
    created = 0

    for event in events:
        event_id = event.get('eventId')
        venue_id = event.get('venueId')
        if not event_id or not venue_id:
            continue

        seats = fetch_seats_for_venue(seat_service_url, venue_id)
        for seat in seats:
            seat_id = resolve_seat_id(seat)
            if not seat_id:
                continue

            existing = SeatInventory.query.filter_by(eventId=event_id, seatId=seat_id).first()
            if existing:
                continue

            db.session.add(SeatInventory(eventId=event_id, seatId=seat_id, status='available'))
            created += 1

    db.session.commit()
    print(f'Seed complete. Created {created} inventory record(s).')
