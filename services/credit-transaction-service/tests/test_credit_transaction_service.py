def create_transaction(
    client,
    user_id='user-1',
    delta=10.0,
    reason='topup',
    reference_id=None,
):
    payload = {
        'userId': user_id,
        'delta': delta,
        'reason': reason,
    }
    if reference_id is not None:
        payload['referenceId'] = reference_id
    return client.post('/credit-transactions', json=payload)


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_create_credit_transaction(client):
    response = create_transaction(
        client,
        user_id='u-123',
        delta=-25.5,
        reason='ticket_purchase',
        reference_id='ticket-001',
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['userId'] == 'u-123'
    assert payload['delta'] == -25.5
    assert payload['reason'] == 'ticket_purchase'
    assert payload['referenceId'] == 'ticket-001'
    assert payload['txnId']
    assert payload['createdAt']


def test_get_transactions_by_user_paginated(client):
    create_transaction(client, user_id='u-main', delta=10.0, reason='topup', reference_id='ref-1')
    create_transaction(client, user_id='u-main', delta=-2.0, reason='ticket_purchase', reference_id='ref-2')
    create_transaction(client, user_id='u-main', delta=-3.0, reason='transfer_credit', reference_id='ref-3')
    create_transaction(client, user_id='u-other', delta=100.0, reason='topup', reference_id='other-ref')

    first_page = client.get('/credit-transactions/user/u-main?page=1&limit=2')
    assert first_page.status_code == 200
    first_payload = first_page.get_json()
    assert first_payload['pagination'] == {'page': 1, 'limit': 2, 'total': 3}
    assert len(first_payload['transactions']) == 2
    assert all(t['userId'] == 'u-main' for t in first_payload['transactions'])

    second_page = client.get('/credit-transactions/user/u-main?page=2&limit=2')
    assert second_page.status_code == 200
    second_payload = second_page.get_json()
    assert second_payload['pagination'] == {'page': 2, 'limit': 2, 'total': 3}
    assert len(second_payload['transactions']) == 1
    assert second_payload['transactions'][0]['userId'] == 'u-main'


def test_get_credit_transaction_by_reference(client):
    created = create_transaction(
        client,
        user_id='u-ref',
        delta=50.0,
        reason='topup',
        reference_id='pi_12345',
    ).get_json()

    response = client.get('/credit-transactions/reference/pi_12345')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['txnId'] == created['txnId']
    assert payload['referenceId'] == 'pi_12345'


def test_get_credit_transaction_by_reference_not_found(client):
    response = client.get('/credit-transactions/reference/missing-reference')

    assert response.status_code == 404
    payload = response.get_json()
    assert payload['error']['code'] == 'TRANSACTION_NOT_FOUND'


def test_pagination_edge_cases(client):
    create_transaction(client, user_id='u-limit', delta=1.0, reason='topup', reference_id='l-1')
    create_transaction(client, user_id='u-limit', delta=2.0, reason='topup', reference_id='l-2')

    capped_limit = client.get('/credit-transactions/user/u-limit?page=1&limit=999')
    assert capped_limit.status_code == 200
    capped_payload = capped_limit.get_json()
    assert capped_payload['pagination']['limit'] == 100
    assert capped_payload['pagination']['total'] == 2
    assert len(capped_payload['transactions']) == 2

    bad_page = client.get('/credit-transactions/user/u-limit?page=0&limit=20')
    assert bad_page.status_code == 400
    assert bad_page.get_json()['error']['code'] == 'VALIDATION_ERROR'

    bad_limit = client.get('/credit-transactions/user/u-limit?page=1&limit=0')
    assert bad_limit.status_code == 400
    assert bad_limit.get_json()['error']['code'] == 'VALIDATION_ERROR'


def test_create_credit_transaction_missing_fields(client):
    response = client.post(
        '/credit-transactions',
        json={
            'userId': 'u-999',
            'delta': 10.0,
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error']['code'] == 'VALIDATION_ERROR'
