"""
Quick gRPC test script for Inventory Service.
Run: docker compose exec inventory-service python /app/test_grpc.py
"""

import sys
sys.path.insert(0, "/app")

import grpc
from src.proto import inventory_pb2, inventory_pb2_grpc

SEAT_ID = "55555555-5555-5555-5555-555555555101"  # Row A, Seat 1
USER_ID = "41414141-4141-4141-4141-414141414141"  # Normal user
NEW_OWNER = "42424242-4242-4242-4242-424242424242"  # High-risk user

def main():
    channel = grpc.insecure_channel("localhost:50051")
    stub = inventory_pb2_grpc.InventoryServiceStub(channel)

    print("=" * 60)
    print("Inventory Service — gRPC Integration Test")
    print("=" * 60)

    # 1. GetSeatOwner — should be empty (no owner yet)
    print("\n[1] GetSeatOwner (before reserve)...")
    resp = stub.GetSeatOwner(inventory_pb2.GetSeatOwnerRequest(seat_id=SEAT_ID))
    print(f"    owner_user_id={resp.owner_user_id!r}, status={resp.status!r}")
    assert resp.status == "AVAILABLE", f"Expected AVAILABLE, got {resp.status}"
    print("    ✅ PASS")

    # 2. ReserveSeat
    print("\n[2] ReserveSeat...")
    resp = stub.ReserveSeat(inventory_pb2.ReserveSeatRequest(seat_id=SEAT_ID, user_id=USER_ID))
    print(f"    success={resp.success}, held_until={resp.held_until}")
    assert resp.success, "Reserve should succeed"
    print("    ✅ PASS")

    # 3. ReserveSeat again — should fail (seat is HELD, not AVAILABLE)
    print("\n[3] ReserveSeat (duplicate)...")
    try:
        resp = stub.ReserveSeat(inventory_pb2.ReserveSeatRequest(seat_id=SEAT_ID, user_id=USER_ID))
        print(f"    success={resp.success}")
        assert not resp.success, "Duplicate reserve should not succeed"
        print("    ✅ PASS (returned success=false)")
    except grpc.RpcError as e:
        print(f"    ✅ PASS (gRPC error: {e.code()}: {e.details()})")

    # 4. VerifyTicket — should show HELD
    print("\n[4] VerifyTicket (while HELD)...")
    resp = stub.VerifyTicket(inventory_pb2.VerifyTicketRequest(seat_id=SEAT_ID))
    print(f"    status={resp.status}, owner={resp.owner_user_id}, event={resp.event_id}")
    assert resp.status == "HELD", f"Expected HELD, got {resp.status}"
    print("    ✅ PASS")

    # 5. ConfirmSeat
    print("\n[5] ConfirmSeat...")
    resp = stub.ConfirmSeat(inventory_pb2.ConfirmSeatRequest(seat_id=SEAT_ID, user_id=USER_ID))
    print(f"    success={resp.success}")
    assert resp.success, "Confirm should succeed"
    print("    ✅ PASS")

    # 6. GetSeatOwner — should now have the user
    print("\n[6] GetSeatOwner (after confirm)...")
    resp = stub.GetSeatOwner(inventory_pb2.GetSeatOwnerRequest(seat_id=SEAT_ID))
    print(f"    owner_user_id={resp.owner_user_id!r}, status={resp.status!r}")
    assert resp.status == "SOLD", f"Expected SOLD, got {resp.status}"
    assert resp.owner_user_id == USER_ID
    print("    ✅ PASS")

    # 7. UpdateOwner (P2P transfer)
    print("\n[7] UpdateOwner (P2P transfer)...")
    resp = stub.UpdateOwner(inventory_pb2.UpdateOwnerRequest(seat_id=SEAT_ID, new_owner_id=NEW_OWNER))
    print(f"    success={resp.success}")
    assert resp.success, "UpdateOwner should succeed"
    print("    ✅ PASS")

    # 8. GetSeatOwner — verify new owner
    print("\n[8] GetSeatOwner (after transfer)...")
    resp = stub.GetSeatOwner(inventory_pb2.GetSeatOwnerRequest(seat_id=SEAT_ID))
    print(f"    owner_user_id={resp.owner_user_id!r}, status={resp.status!r}")
    assert resp.owner_user_id == NEW_OWNER
    print("    ✅ PASS")

    # 9. MarkCheckedIn
    print("\n[9] MarkCheckedIn...")
    resp = stub.MarkCheckedIn(inventory_pb2.MarkCheckedInRequest(seat_id=SEAT_ID))
    print(f"    success={resp.success}")
    assert resp.success, "MarkCheckedIn should succeed"
    print("    ✅ PASS")

    # 10. MarkCheckedIn again — should fail (DUPLICATE)
    print("\n[10] MarkCheckedIn (duplicate)...")
    try:
        resp = stub.MarkCheckedIn(inventory_pb2.MarkCheckedInRequest(seat_id=SEAT_ID))
        print(f"    success={resp.success}")
        assert not resp.success, "Duplicate check-in should fail"
        print("    ✅ PASS (returned success=false)")
    except grpc.RpcError as e:
        print(f"    ✅ PASS (gRPC error: {e.code()}: {e.details()})")

    # 11. Test with a second seat — full reserve → release cycle
    SEAT_2 = "55555555-5555-5555-5555-555555555102"  # Row A, Seat 2
    print("\n[11] Reserve + Release cycle (Seat A2)...")
    resp = stub.ReserveSeat(inventory_pb2.ReserveSeatRequest(seat_id=SEAT_2, user_id=USER_ID))
    assert resp.success, "Reserve A2 should succeed"
    resp = stub.ReleaseSeat(inventory_pb2.ReleaseSeatRequest(seat_id=SEAT_2))
    assert resp.success, "Release A2 should succeed"
    resp = stub.GetSeatOwner(inventory_pb2.GetSeatOwnerRequest(seat_id=SEAT_2))
    assert resp.status == "AVAILABLE", f"Expected AVAILABLE after release, got {resp.status}"
    print("    ✅ PASS (reserve → release → AVAILABLE)")

    print("\n" + "=" * 60)
    print("ALL 11 TESTS PASSED ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
