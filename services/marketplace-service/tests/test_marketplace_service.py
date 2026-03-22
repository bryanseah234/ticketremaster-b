def create_listing(client, ticket_id='ticket-1', seller_id='seller-1', price=120.5):
    return client.post(
        '/listings',
        json={
            'ticketId': ticket_id,
            'sellerId': seller_id,
            'price': price,
        },
    )


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_create_listing(client):
    response = create_listing(client)

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['ticketId'] == 'ticket-1'
    assert payload['sellerId'] == 'seller-1'
    assert payload['price'] == 120.5
    assert payload['status'] == 'active'
    assert 'listingId' in payload
    assert 'createdAt' in payload


def test_get_all_active_listings(client):
    create_listing(client, ticket_id='ticket-1')
    create_listing(client, ticket_id='ticket-2')

    response = client.get('/listings')

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload['listings']) == 2
    # createdAt desc, second inserted appears first
    assert payload['listings'][0]['ticketId'] == 'ticket-2'
    assert payload['listings'][1]['ticketId'] == 'ticket-1'


def test_get_listing_by_id(client):
    created = create_listing(client).get_json()

    response = client.get(f"/listings/{created['listingId']}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['listingId'] == created['listingId']
    assert payload['status'] == 'active'


def test_patch_listing_status(client):
    created = create_listing(client).get_json()

    response = client.patch(
        f"/listings/{created['listingId']}",
        json={'status': 'completed'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['listingId'] == created['listingId']
    assert payload['status'] == 'completed'


def test_get_listing_not_found_returns_404(client):
    response = client.get('/listings/nonexistent-id')

    assert response.status_code == 404
    error = response.get_json()['error']
    assert error['code'] == 'LISTING_NOT_FOUND'


def test_patch_listing_not_found_returns_404(client):
    response = client.patch('/listings/nonexistent-id', json={'status': 'cancelled'})

    assert response.status_code == 404
    error = response.get_json()['error']
    assert error['code'] == 'LISTING_NOT_FOUND'


def test_listings_only_returns_active(client):
    active_listing = create_listing(client, ticket_id='active-ticket').get_json()
    completed_listing = create_listing(client, ticket_id='completed-ticket').get_json()

    client.patch(
        f"/listings/{completed_listing['listingId']}",
        json={'status': 'completed'},
    )

    response = client.get('/listings')

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload['listings']) == 1
    assert payload['listings'][0]['listingId'] == active_listing['listingId']
    assert payload['listings'][0]['status'] == 'active'
