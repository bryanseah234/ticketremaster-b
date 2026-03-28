from app import db
from models import Venue


def add_venue(
    venue_id,
    name,
    capacity=1000,
    address='1 Test Street',
    postal_code='000001',
    coordinates='1.3000,103.8000',
    is_active=True,
):
    venue = Venue(
        venueId=venue_id,
        name=name,
        capacity=capacity,
        address=address,
        postalCode=postal_code,
        coordinates=coordinates,
        isActive=is_active,
    )
    db.session.add(venue)
    db.session.commit()
    return venue


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_list_venues_empty(client):
    response = client.get('/venues')

    assert response.status_code == 200
    assert response.get_json() == {'venues': []}


def test_list_venues_returns_seeded_like_data_ordered_and_active_only(client, app):
    with app.app_context():
        add_venue(
            venue_id='ven_002',
            name='Singapore Indoor Stadium',
            capacity=12000,
            address='2 Stadium Walk',
            postal_code='397691',
            coordinates='1.3006,103.8745',
            is_active=True,
        )
        add_venue(
            venue_id='ven_001',
            name='Esplanade Concert Hall',
            capacity=1800,
            address='1 Esplanade Dr',
            postal_code='038981',
            coordinates='1.2897,103.8555',
            is_active=True,
        )
        add_venue(
            venue_id='ven_999',
            name='Zeta Inactive Venue',
            is_active=False,
        )

    response = client.get('/venues')

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload['venues']) == 2
    assert payload['venues'][0]['venueId'] == 'ven_001'
    assert payload['venues'][0]['name'] == 'Esplanade Concert Hall'
    assert payload['venues'][1]['venueId'] == 'ven_002'
    assert payload['venues'][1]['name'] == 'Singapore Indoor Stadium'


def test_get_venue_by_id(client, app):
    with app.app_context():
        add_venue(
            venue_id='ven_001',
            name='Esplanade Concert Hall',
            capacity=1800,
            address='1 Esplanade Dr',
            postal_code='038981',
            coordinates='1.2897,103.8555',
            is_active=True,
        )

    response = client.get('/venues/ven_001')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['venueId'] == 'ven_001'
    assert payload['name'] == 'Esplanade Concert Hall'
    assert payload['capacity'] == 1800
    assert payload['address'] == '1 Esplanade Dr'
    assert payload['postalCode'] == '038981'
    assert payload['coordinates'] == '1.2897,103.8555'
    assert payload['isActive'] is True
    assert 'createdAt' in payload


def test_get_venue_not_found(client):
    response = client.get('/venues/unknown')

    assert response.status_code == 404
    payload = response.get_json()
    assert payload['error']['code'] == 'VENUE_NOT_FOUND'
    assert payload['error']['message'] == 'Venue not found'
    assert payload['error']['status'] == 404
    assert payload['error']['details']['path'] == '/venues/unknown'


def test_list_venues_filters_inactive_records(client, app):
    with app.app_context():
        add_venue('ven_active', 'Active Venue', is_active=True)
        add_venue('ven_inactive', 'Inactive Venue', is_active=False)

    response = client.get('/venues')

    assert response.status_code == 200
    payload = response.get_json()
    venue_ids = [venue['venueId'] for venue in payload['venues']]
    assert venue_ids == ['ven_active']
