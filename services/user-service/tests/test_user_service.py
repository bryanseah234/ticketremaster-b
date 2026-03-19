def create_user(client, email='jane@example.com'):
    return client.post(
        '/users',
        json={
            'email': email,
            'password': 'hashed-password',
            'salt': 'salt-value',
            'phoneNumber': '+6591234567',
        },
    )


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_list_users_returns_created_users(client):
    create_user(client, email='a@example.com')
    create_user(client, email='b@example.com')

    response = client.get('/users')

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload) == 2
    assert payload[0]['email'] == 'a@example.com'
    assert payload[1]['email'] == 'b@example.com'
    assert 'password' not in payload[0]
    assert 'salt' not in payload[0]


def test_create_user(client):
    response = create_user(client)

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['email'] == 'jane@example.com'
    assert payload['role'] == 'user'
    assert payload['isFlagged'] is False
    assert 'password' not in payload
    assert 'salt' not in payload


def test_reject_duplicate_email(client):
    create_user(client)

    response = create_user(client)

    assert response.status_code == 409
    assert response.get_json()['error']['code'] == 'EMAIL_ALREADY_EXISTS'


def test_get_user_by_id_includes_full_record(client):
    created = create_user(client).get_json()

    response = client.get(f"/users/{created['userId']}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['email'] == 'jane@example.com'
    assert payload['password'] == 'hashed-password'
    assert payload['salt'] == 'salt-value'


def test_patch_user_updates_allowed_fields(client):
    created = create_user(client).get_json()

    response = client.patch(
        f"/users/{created['userId']}",
        json={'phoneNumber': '+6588888888', 'isFlagged': True},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['phoneNumber'] == '+6588888888'
    assert payload['isFlagged'] is True
    assert payload['password'] == 'hashed-password'
    assert payload['salt'] == 'salt-value'


def test_get_user_by_email_includes_sensitive_fields(client):
    create_user(client)

    response = client.get('/users/by-email/jane@example.com')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['password'] == 'hashed-password'
    assert payload['salt'] == 'salt-value'
