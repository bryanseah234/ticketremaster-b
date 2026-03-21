from types import SimpleNamespace

import routes


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_payment_intent_success(client, monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(client_secret="cs_test_123", id="pi_test_123")

    monkeypatch.setattr(routes.stripe.PaymentIntent, "create", fake_create)

    response = client.post(
        "/stripe/create-payment-intent", json={"amount": 50, "userId": "user-1"}
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "clientSecret": "cs_test_123",
        "paymentIntentId": "pi_test_123",
        "amount": 50,
    }
    assert captured == {
        "amount": 5000,
        "currency": "sgd",
        "metadata": {"userId": "user-1", "credits": "50"},
    }


def test_create_payment_intent_missing_fields(client):
    response = client.post("/stripe/create-payment-intent", json={"amount": 10})

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_create_payment_intent_invalid_amount(client):
    response = client.post(
        "/stripe/create-payment-intent", json={"amount": 0, "userId": "user-1"}
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_webhook_success_payment_intent_succeeded(client, monkeypatch):
    def fake_construct_event(payload, signature, secret):
        assert payload == b'{"id":"evt_123"}'
        assert signature == "sig_test"
        assert secret == "whsec_test_fake"
        return {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "metadata": {"userId": "user-1", "credits": "50"},
                }
            },
        }

    monkeypatch.setattr(routes.stripe.Webhook, "construct_event", fake_construct_event)

    response = client.post(
        "/stripe/webhook",
        data=b'{"id":"evt_123"}',
        headers={"Stripe-Signature": "sig_test"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "received": True,
        "userId": "user-1",
        "credits": "50",
        "paymentIntentId": "pi_123",
    }


def test_webhook_invalid_signature(client, monkeypatch):
    def fake_construct_event(payload, signature, secret):
        raise Exception("Invalid signature")

    monkeypatch.setattr(routes.stripe.Webhook, "construct_event", fake_construct_event)

    response = client.post(
        "/stripe/webhook",
        data=b"{}",
        headers={"Stripe-Signature": "bad_sig"},
        content_type="application/json",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"]["code"] == "INVALID_SIGNATURE"
    assert payload["error"]["message"] == "Invalid signature"
    assert payload["error"]["status"] == 400
    assert "traceId" in payload["error"]
    assert payload["error"]["details"]["method"] == "POST"
    assert payload["error"]["details"]["path"] == "/stripe/webhook"
