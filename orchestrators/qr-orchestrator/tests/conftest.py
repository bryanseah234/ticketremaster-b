import os, sys, pathlib
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("OUTSYSTEMS_API_KEY", "test-key")
os.environ.setdefault("CREDIT_SERVICE_URL", "http://credit-mock")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from app import create_app

@pytest.fixture()
def app():
    return create_app({"TESTING": True})

@pytest.fixture()
def client(app):
    return app.test_client()
