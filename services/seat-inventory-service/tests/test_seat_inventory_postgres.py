import os
from concurrent.futures import ThreadPoolExecutor

import grpc
import pytest
from concurrent import futures

from app import create_app, db
from grpc_server import SeatInventoryGrpcService
from models import SeatInventory
from seat_inventory_pb2 import HoldSeatRequest
from seat_inventory_pb2_grpc import SeatInventoryServiceStub, add_SeatInventoryServiceServicer_to_server


@pytest.mark.skipif(
    not os.getenv('SEAT_INVENTORY_POSTGRES_TEST_URL'),
    reason='SEAT_INVENTORY_POSTGRES_TEST_URL not configured',
)
def test_postgres_concurrent_hold_only_one_wins():
    app = create_app(
        {
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': os.environ['SEAT_INVENTORY_POSTGRES_TEST_URL'],
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        }
    )

    with app.app_context():
        db.drop_all()
        db.create_all()
        inventory = SeatInventory(eventId='evt_pg_1', seatId='A1', status='available')
        db.session.add(inventory)
        db.session.commit()
        inventory_id = inventory.inventoryId

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    add_SeatInventoryServiceServicer_to_server(SeatInventoryGrpcService(flask_app=app), server)
    port = server.add_insecure_port('127.0.0.1:0')
    server.start()
    channel = grpc.insecure_channel(f'127.0.0.1:{port}')
    stub = SeatInventoryServiceStub(channel)

    try:
        def attempt(user_id):
            return stub.HoldSeat(
                HoldSeatRequest(inventory_id=inventory_id, user_id=user_id, hold_duration_seconds=120)
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(attempt, 'pg-user-a').result()
            b = pool.submit(attempt, 'pg-user-b').result()

        assert [a.success, b.success].count(True) == 1
        assert [a.success, b.success].count(False) == 1
    finally:
        channel.close()
        server.stop(grace=1)

    with app.app_context():
        db.drop_all()
