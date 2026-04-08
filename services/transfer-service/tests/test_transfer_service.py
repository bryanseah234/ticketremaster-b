def create_transfer(client, **overrides):
    payload = {
        'listingId': 'listing-123',
        'buyerId': 'buyer-123',
        'sellerId': 'seller-123',
        'creditAmount': 125.5,
    }
    payload.update(overrides)
    return client.post('/transfers', json=payload)


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_create_transfer(client):
    response = create_transfer(client, buyerVerificationSid='VE12345')

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['status'] == 'pending_seller_acceptance'
    assert payload['transferId']
    assert payload['createdAt']


def test_create_transfer_validates_required_fields(client):
    response = client.post('/transfers', json={'listingId': 'listing-123'})

    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'VALIDATION_ERROR'


def test_get_transfer_by_id(client):
    created = create_transfer(client).get_json()

    response = client.get(f"/transfers/{created['transferId']}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['transferId'] == created['transferId']
    assert payload['listingId'] == 'listing-123'
    assert payload['buyerOtpVerified'] is False
    assert payload['sellerOtpVerified'] is False
    assert payload['completedAt'] is None


def test_get_transfer_not_found(client):
    response = client.get('/transfers/missing-transfer-id')

    assert response.status_code == 404
    error = response.get_json()['error']
    assert error['code'] == 'TRANSFER_NOT_FOUND'


def test_patch_transfer_updates_status_and_otp_flags_and_sids(client):
    created = create_transfer(client).get_json()

    response = client.patch(
        f"/transfers/{created['transferId']}",
        json={
            'status': 'pending_seller_otp',
            'buyerOtpVerified': True,
            'sellerOtpVerified': True,
            'buyerVerificationSid': 'VE-buyer-1',
            'sellerVerificationSid': 'VE-seller-1',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'pending_seller_otp'
    assert payload['buyerOtpVerified'] is True
    assert payload['sellerOtpVerified'] is True
    assert payload['buyerVerificationSid'] == 'VE-buyer-1'
    assert payload['sellerVerificationSid'] == 'VE-seller-1'


def test_patch_transfer_parses_completed_at_iso_string(client):
    created = create_transfer(client).get_json()

    response = client.patch(
        f"/transfers/{created['transferId']}",
        json={'status': 'completed', 'completedAt': '2026-03-20T12:30:00Z'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'completed'
    assert payload['completedAt'].startswith('2026-03-20T12:30:00')


def test_patch_transfer_not_found(client):
    response = client.patch('/transfers/missing-transfer-id', json={'status': 'cancelled'})

    assert response.status_code == 404
    error = response.get_json()['error']
    assert error['code'] == 'TRANSFER_NOT_FOUND'


def test_patch_transfer_rejects_empty_body(client):
    created = create_transfer(client).get_json()

    response = client.patch(f"/transfers/{created['transferId']}", json={})

    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'VALIDATION_ERROR'


def test_list_transfers_by_buyer_id(client):
    first = create_transfer(client, buyerId='buyer-lookup-001', sellerId='seller-lookup-001').get_json()
    create_transfer(client, buyerId='buyer-other-001', sellerId='seller-other-001')

    response = client.get('/transfers', query_string={
        'buyerId': 'buyer-lookup-001',
        'status': 'pending_seller_acceptance',
    })

    assert response.status_code == 200
    payload = response.get_json()['transfers']
    assert len(payload) == 1
    assert payload[0]['transferId'] == first['transferId']
