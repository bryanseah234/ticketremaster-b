import os
import grpc
import uuid
from flask import request
from src import inventory_pb2
from src import inventory_pb2_grpc

INVENTORY_URL = os.environ.get("INVENTORY_SERVICE_URL", "inventory-service:50051")

def get_grpc_metadata():
    try:
        correlation_id = request.headers.get("X-Correlation-ID") or getattr(request, "correlation_id", str(uuid.uuid4()))
        return (('correlation-id', correlation_id),)
    except RuntimeError:
        return (('correlation-id', str(uuid.uuid4())),)

class InventoryClient:
    def __init__(self):
        self.channel = grpc.insecure_channel(INVENTORY_URL)
        self.stub = inventory_pb2_grpc.InventoryServiceStub(self.channel)

    def reserve_seat(self, seat_id: str, user_id: str):
        req = inventory_pb2.ReserveSeatRequest(seat_id=seat_id, user_id=user_id)
        return self.stub.ReserveSeat(req, metadata=get_grpc_metadata())

    def confirm_seat(self, seat_id: str, user_id: str):
        req = inventory_pb2.ConfirmSeatRequest(seat_id=seat_id, user_id=user_id)
        return self.stub.ConfirmSeat(req, metadata=get_grpc_metadata())

    def release_seat(self, seat_id: str):
        req = inventory_pb2.ReleaseSeatRequest(seat_id=seat_id)
        return self.stub.ReleaseSeat(req, metadata=get_grpc_metadata())

    def update_owner(self, seat_id: str, new_owner_id: str):
        req = inventory_pb2.UpdateOwnerRequest(seat_id=seat_id, new_owner_id=new_owner_id)
        return self.stub.UpdateOwner(req, metadata=get_grpc_metadata())

    def verify_ticket(self, seat_id: str):
        req = inventory_pb2.VerifyTicketRequest(seat_id=seat_id)
        return self.stub.VerifyTicket(req, metadata=get_grpc_metadata())

    def mark_checked_in(self, seat_id: str):
        req = inventory_pb2.MarkCheckedInRequest(seat_id=seat_id)
        return self.stub.MarkCheckedIn(req, metadata=get_grpc_metadata())

    def get_seat_owner(self, seat_id: str):
        req = inventory_pb2.GetSeatOwnerRequest(seat_id=seat_id)
        return self.stub.GetSeatOwner(req, metadata=get_grpc_metadata())

    def list_seat(self, seat_id: str, seller_user_id: str):
        req = inventory_pb2.ListSeatRequest(seat_id=seat_id, seller_user_id=seller_user_id)
        return self.stub.ListSeat(req, metadata=get_grpc_metadata())

inventory_client = InventoryClient()
