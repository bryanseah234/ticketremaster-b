import pathlib
import sys

import grpc
import pytest
from concurrent import futures

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import create_app, db
from grpc_server import SeatInventoryGrpcService
from models import SeatInventory
from seat_inventory_pb2_grpc import SeatInventoryServiceStub, add_SeatInventoryServiceServicer_to_server


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / 'seat_inventory_test.sqlite'
    app = create_app(
        {
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seeded_inventory(app):
    with app.app_context():
        inventory = SeatInventory(eventId='evt_001', seatId='A1', status='available')
        second_inventory = SeatInventory(eventId='evt_001', seatId='A2', status='available')
        db.session.add(inventory)
        db.session.add(second_inventory)
        db.session.commit()
        return inventory.inventoryId, second_inventory.inventoryId


@pytest.fixture()
def grpc_stub(app):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    add_SeatInventoryServiceServicer_to_server(SeatInventoryGrpcService(flask_app=app), server)
    port = server.add_insecure_port('127.0.0.1:0')
    server.start()

    channel = grpc.insecure_channel(f'127.0.0.1:{port}')
    try:
        yield SeatInventoryServiceStub(channel)
    finally:
        channel.close()
        server.stop(grace=1)
