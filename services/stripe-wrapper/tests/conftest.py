import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import create_app


@pytest.fixture()
def app():
    app = create_app(
        {
            'TESTING': True,
            'STRIPE_SECRET_KEY': 'sk_test_fake',
            'STRIPE_WEBHOOK_SECRET': 'whsec_test_fake',
        }
    )
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()
