from app import db
from models import Seat


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_get_seats_for_venue_returns_empty_list_when_no_seats(client):
    response = client.get('/seats/venue/ven_001')

    assert response.status_code == 200
    assert response.get_json() == {'seats': []}


def test_get_seats_for_venue_returns_seeded_data_shape(client, app):
    with app.app_context():
        db.session.add_all(
            [
                Seat(venueId='ven_001', seatNumber='A1', rowNumber='A'),
                Seat(venueId='ven_001', seatNumber='A2', rowNumber='A'),
                Seat(venueId='ven_002', seatNumber='A1', rowNumber='A'),
            ]
        )
        db.session.commit()

    response = client.get('/seats/venue/ven_001')

    assert response.status_code == 200
    payload = response.get_json()
    assert list(payload.keys()) == ['seats']
    assert len(payload['seats']) == 2
    assert payload['seats'][0]['venueId'] == 'ven_001'
    assert payload['seats'][1]['venueId'] == 'ven_001'


def test_get_seats_for_venue_orders_by_row_then_seat_number(client, app):
    with app.app_context():
        db.session.add_all(
            [
                Seat(venueId='ven_001', seatNumber='C2', rowNumber='C'),
                Seat(venueId='ven_001', seatNumber='A2', rowNumber='A'),
                Seat(venueId='ven_001', seatNumber='B1', rowNumber='B'),
                Seat(venueId='ven_001', seatNumber='A1', rowNumber='A'),
            ]
        )
        db.session.commit()

    response = client.get('/seats/venue/ven_001')

    assert response.status_code == 200
    seats = response.get_json()['seats']
    assert [(seat['rowNumber'], seat['seatNumber']) for seat in seats] == [
        ('A', 'A1'),
        ('A', 'A2'),
        ('B', 'B1'),
        ('C', 'C2'),
    ]
