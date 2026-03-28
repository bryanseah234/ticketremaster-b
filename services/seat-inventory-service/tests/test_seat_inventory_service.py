from concurrent.futures import ThreadPoolExecutor

from seat_inventory_pb2 import GetSeatStatusRequest, HoldSeatRequest, ReleaseSeatRequest, SellSeatRequest


def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_list_inventory_by_event(client, seeded_inventory):
    response = client.get('/inventory/event/evt_001')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['eventId'] == 'evt_001'
    assert len(payload['inventory']) == 2
    assert payload['inventory'][0]['seatId'] == 'A1'


def test_create_inventory_batch(client):
    response = client.post(
        '/inventory/batch',
        json={
            'eventId': 'evt_002',
            'seats': [
                {'seatId': 'B1'},
                {'seatId': 'B2', 'status': 'held'},
            ],
        },
    )

    assert response.status_code == 201
    assert response.get_json()['data'] == {'eventId': 'evt_002', 'createdCount': 2}


def test_create_inventory_batch_rejects_invalid_seat_payload(client):
    response = client.post(
        '/inventory/batch',
        json={
            'eventId': 'evt_002',
            'seats': ['B1'],
        },
    )

    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'VALIDATION_ERROR'


def test_create_inventory_batch_requires_seat_id(client):
    response = client.post(
        '/inventory/batch',
        json={
            'eventId': 'evt_002',
            'seats': [{}],
        },
    )

    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'VALIDATION_ERROR'


def test_hold_seat_success(grpc_stub, seeded_inventory):
    inventory_id, _ = seeded_inventory

    response = grpc_stub.HoldSeat(
        HoldSeatRequest(inventory_id=inventory_id, user_id='user-123', hold_duration_seconds=120)
    )

    assert response.success is True
    assert response.status == 'held'
    assert response.error_code == ''
    assert response.held_until
    assert response.hold_token


def test_release_seat_success(grpc_stub, seeded_inventory):
    inventory_id, _ = seeded_inventory

    hold = grpc_stub.HoldSeat(
        HoldSeatRequest(inventory_id=inventory_id, user_id='user-123', hold_duration_seconds=120)
    )
    assert hold.success is True

    released = grpc_stub.ReleaseSeat(
        ReleaseSeatRequest(inventory_id=inventory_id, user_id='user-123', hold_token=hold.hold_token)
    )
    assert released.success is True

    status = grpc_stub.GetSeatStatus(GetSeatStatusRequest(inventory_id=inventory_id))
    assert status.status == 'available'
    assert status.held_until == ''


def test_sell_seat_success(grpc_stub, seeded_inventory):
    inventory_id, _ = seeded_inventory

    hold = grpc_stub.HoldSeat(
        HoldSeatRequest(inventory_id=inventory_id, user_id='user-123', hold_duration_seconds=120)
    )
    sold = grpc_stub.SellSeat(
        SellSeatRequest(inventory_id=inventory_id, user_id='user-123', hold_token=hold.hold_token)
    )
    assert sold.success is True

    status = grpc_stub.GetSeatStatus(GetSeatStatusRequest(inventory_id=inventory_id))
    assert status.status == 'sold'


def test_get_seat_status_not_found(grpc_stub):
    status = grpc_stub.GetSeatStatus(GetSeatStatusRequest(inventory_id='missing-id'))
    assert status.status == 'not_found'


def test_sell_seat_fails_without_matching_hold(grpc_stub, seeded_inventory):
    inventory_id, _ = seeded_inventory
    sold = grpc_stub.SellSeat(
        SellSeatRequest(inventory_id=inventory_id, user_id='user-x', hold_token='no-hold')
    )
    assert sold.success is False


def test_hold_seat_race_condition_only_one_succeeds(grpc_stub, seeded_inventory):
    inventory_id, _ = seeded_inventory

    def attempt_hold(user_id):
        return grpc_stub.HoldSeat(
            HoldSeatRequest(inventory_id=inventory_id, user_id=user_id, hold_duration_seconds=120)
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(attempt_hold, 'user-a')
        future_b = pool.submit(attempt_hold, 'user-b')
        first = future_a.result()
        second = future_b.result()

    successes = [result.success for result in (first, second)]
    assert successes.count(True) == 1
    assert successes.count(False) == 1


def test_stale_release_does_not_clear_newer_hold(grpc_stub, seeded_inventory):
    inventory_id, _ = seeded_inventory

    first_hold = grpc_stub.HoldSeat(
        HoldSeatRequest(inventory_id=inventory_id, user_id='user-a', hold_duration_seconds=120)
    )
    assert first_hold.success is True

    stale_release = grpc_stub.ReleaseSeat(
        ReleaseSeatRequest(inventory_id=inventory_id, user_id='user-a', hold_token='wrong-token')
    )
    assert stale_release.success is False

    release = grpc_stub.ReleaseSeat(
        ReleaseSeatRequest(
            inventory_id=inventory_id,
            user_id='user-a',
            hold_token=first_hold.hold_token,
        )
    )
    assert release.success is True

    second_hold = grpc_stub.HoldSeat(
        HoldSeatRequest(inventory_id=inventory_id, user_id='user-b', hold_duration_seconds=120)
    )
    assert second_hold.success is True

    stale_old_release = grpc_stub.ReleaseSeat(
        ReleaseSeatRequest(
            inventory_id=inventory_id,
            user_id='user-a',
            hold_token=first_hold.hold_token,
        )
    )
    assert stale_old_release.success is False

    status = grpc_stub.GetSeatStatus(GetSeatStatusRequest(inventory_id=inventory_id))
    assert status.status == 'held'
