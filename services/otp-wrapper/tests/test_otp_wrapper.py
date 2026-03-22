import requests


class FakeResponse:
    def __init__(self, payload=None, status_code=200, should_raise=False):
        self._payload = payload or {}
        self.status_code = status_code
        self._should_raise = should_raise

    def raise_for_status(self):
        if self._should_raise:
            raise requests.HTTPError('SMU upstream error')

    def json(self):
        return self._payload


def test_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_blueprint_health_check(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_send_otp_success(client, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured['url'] = url
        captured['headers'] = headers
        captured['json'] = json
        captured['timeout'] = timeout
        return FakeResponse({'VerificationSid': 'sid_123', 'Success': True})

    monkeypatch.setattr('routes.requests.post', fake_post)

    response = client.post('/otp/send', json={'phoneNumber': '+6591234567'})

    assert response.status_code == 200
    assert response.get_json() == {'sid': 'sid_123'}
    assert captured['url'] == 'https://smu.example.com/Notification/SendOTP'
    assert captured['headers'] == {'X-API-Key': 'fake-api-key'}
    assert captured['json'] == {'Mobile': '+6591234567'}
    assert captured['timeout'] == 10


def test_send_otp_missing_phone_number(client):
    response = client.post('/otp/send', json={})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error']['code'] == 'VALIDATION_ERROR'


def test_send_otp_upstream_failure(client, monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse(should_raise=True)

    monkeypatch.setattr('routes.requests.post', fake_post)

    response = client.post('/otp/send', json={'phoneNumber': '+6591234567'})

    assert response.status_code == 502
    payload = response.get_json()
    assert payload['error']['code'] == 'OTP_SEND_FAILED'


def test_verify_otp_success(client, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured['url'] = url
        captured['headers'] = headers
        captured['json'] = json
        captured['timeout'] = timeout
        return FakeResponse({'Success': True})

    monkeypatch.setattr('routes.requests.post', fake_post)

    response = client.post('/otp/verify', json={'sid': 'sid_123', 'otp': '123456'})

    assert response.status_code == 200
    assert response.get_json() == {'verified': True}
    assert captured['url'] == 'https://smu.example.com/Notification/VerifyOTP'
    assert captured['headers'] == {'X-API-Key': 'fake-api-key'}
    assert captured['json'] == {'VerificationSid': 'sid_123', 'Code': '123456'}
    assert captured['timeout'] == 10


def test_verify_otp_returns_false(client, monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse({'Success': False})

    monkeypatch.setattr('routes.requests.post', fake_post)

    response = client.post('/otp/verify', json={'sid': 'sid_123', 'otp': '000000'})

    assert response.status_code == 200
    assert response.get_json() == {'verified': False}


def test_verify_otp_returns_false_on_upstream_400(client, monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse({'Errors': ['invalid code']}, status_code=400)

    monkeypatch.setattr('routes.requests.post', fake_post)

    response = client.post('/otp/verify', json={'sid': 'sid_123', 'otp': '000000'})

    assert response.status_code == 200
    assert response.get_json() == {'verified': False}


def test_verify_otp_missing_fields(client):
    response = client.post('/otp/verify', json={'sid': 'sid_123'})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error']['code'] == 'VALIDATION_ERROR'


def test_verify_otp_upstream_failure(client, monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.RequestException('network failure')

    monkeypatch.setattr('routes.requests.post', fake_post)

    response = client.post('/otp/verify', json={'sid': 'sid_123', 'otp': '123456'})

    assert response.status_code == 502
    payload = response.get_json()
    assert payload['error']['code'] == 'OTP_VERIFY_FAILED'
