def create_ticket_log(client, ticket_id='ticket-001', staff_id='staff-001', status='checked_in'):
    return client.post(
        '/ticket-logs',
        json={
            'ticketId': ticket_id,
            'staffId': staff_id,
            'status': status,
        },
    )


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_create_ticket_log(client):
    response = create_ticket_log(client)

    assert response.status_code == 201
    payload = response.get_json()
    assert 'logId' in payload
    assert payload['ticketId'] == 'ticket-001'
    assert payload['staffId'] == 'staff-001'
    assert payload['status'] == 'checked_in'
    assert 'timestamp' in payload


def test_get_logs_by_ticket_id_returns_logs_in_desc_timestamp_order(client):
    first = create_ticket_log(client, ticket_id='ticket-xyz', staff_id='staff-001', status='checked_in')
    second = create_ticket_log(client, ticket_id='ticket-xyz', staff_id='staff-002', status='rejected')

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get('/ticket-logs/ticket/ticket-xyz')

    assert response.status_code == 200
    payload = response.get_json()
    assert 'logs' in payload
    assert len(payload['logs']) == 2
    assert payload['logs'][0]['status'] == 'rejected'
    assert payload['logs'][0]['staffId'] == 'staff-002'
    assert payload['logs'][1]['status'] == 'checked_in'
    assert payload['logs'][1]['staffId'] == 'staff-001'


def test_get_logs_by_ticket_id_returns_empty_for_unknown_ticket(client):
    response = client.get('/ticket-logs/ticket/non-existent-ticket')

    assert response.status_code == 200
    assert response.get_json() == {'logs': []}


def test_create_ticket_log_missing_fields_validation(client):
    response = client.post('/ticket-logs', json={'ticketId': 'ticket-001'})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error']['code'] == 'VALIDATION_ERROR'
    assert payload['error']['message'] == 'Missing required fields'
