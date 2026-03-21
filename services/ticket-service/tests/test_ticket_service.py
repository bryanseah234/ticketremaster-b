def ticket_data(**kwargs):
    data = {
        'inventoryId': 'inv_001',
        'ownerId': 'usr_001',
        'venueId': 'ven_001',
        'eventId': 'evt_001',
        'price': 120.5,
    }
    data.update(kwargs)
    return data


def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_create_ticket(client):
    response = client.post('/tickets', json=ticket_data())
    assert response.status_code == 201
    payload = response.get_json()

    assert 'ticketId' in payload
    assert payload['inventoryId'] == 'inv_001'
    assert payload['ownerId'] == 'usr_001'
    assert payload['venueId'] == 'ven_001'
    assert payload['eventId'] == 'evt_001'
    assert payload['price'] == 120.5
    assert payload['status'] == 'active'
    assert payload['qrHash'] is not None
    assert len(payload['qrHash']) == 32
    assert payload['qrTimestamp'] is not None
    assert payload['createdAt'] is not None


def test_get_ticket_by_id(client):
    created = client.post('/tickets', json=ticket_data()).get_json()

    response = client.get(f"/tickets/{created['ticketId']}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ticketId'] == created['ticketId']
    assert payload['ownerId'] == 'usr_001'


def test_get_tickets_by_owner_ordered_desc(client):
    first = client.post('/tickets', json=ticket_data(ownerId='usr_999', inventoryId='inv_a')).get_json()
    second = client.post('/tickets', json=ticket_data(ownerId='usr_999', inventoryId='inv_b')).get_json()

    response = client.get('/tickets/owner/usr_999')
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload['tickets']) == 2
    assert payload['tickets'][0]['ticketId'] == second['ticketId']
    assert payload['tickets'][1]['ticketId'] == first['ticketId']


def test_get_ticket_by_qr_hash(client):
    created = client.post('/tickets', json=ticket_data()).get_json()

    response = client.get(f"/tickets/qr/{created['qrHash']}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ticketId'] == created['ticketId']


def test_patch_ticket(client):
    created = client.post('/tickets', json=ticket_data()).get_json()
    new_timestamp = '2026-01-01T12:00:00+00:00'

    response = client.patch(
        f"/tickets/{created['ticketId']}",
        json={
            'status': 'listed',
            'ownerId': 'usr_002',
            'qrHash': 'abc123def456abc123def456abc123de',
            'qrTimestamp': new_timestamp,
        },
    )
    assert response.status_code == 200

    payload = response.get_json()
    assert payload['ticketId'] == created['ticketId']
    assert payload['status'] == 'listed'
    assert payload['ownerId'] == 'usr_002'
    assert payload['qrHash'] == 'abc123def456abc123def456abc123de'
    assert payload['qrTimestamp'].startswith('2026-01-01T12:00:00')


def test_get_ticket_not_found(client):
    response = client.get('/tickets/does-not-exist')
    assert response.status_code == 404
    error = response.get_json()['error']
    assert error['code'] == 'TICKET_NOT_FOUND'
    assert error['message'] == 'Ticket not found'


def test_get_ticket_by_qr_not_found(client):
    response = client.get('/tickets/qr/not-found-hash')
    assert response.status_code == 404
    error = response.get_json()['error']
    assert error['code'] == 'TICKET_NOT_FOUND'


def test_patch_ticket_not_found(client):
    response = client.patch('/tickets/does-not-exist', json={'status': 'used'})
    assert response.status_code == 404
    error = response.get_json()['error']
    assert error['code'] == 'TICKET_NOT_FOUND'
