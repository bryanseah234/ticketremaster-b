"""
gRPC Server — Inventory Service
Implements InventoryServiceServicer, tying all service functions together.
"""

import grpc
from concurrent import futures
import logging

from src.proto import inventory_pb2
from src.proto import inventory_pb2_grpc
from src.db import get_session
from src.services import lock_service, ownership_service, verification_service

logger = logging.getLogger(__name__)


class InventoryServiceServicer(inventory_pb2_grpc.InventoryServiceServicer):
    """gRPC servicer for the Inventory Service."""

    def ReserveSeat(self, request, context):
        logger.info(f"ReserveSeat: seat_id={request.seat_id}, user_id={request.user_id}")
        with get_session() as session:
            success, held_until, error = lock_service.reserve_seat(
                session, request.seat_id, request.user_id
            )

        if not success:
            if error == "SEAT_NOT_FOUND":
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Seat not found")
            elif error == "SEAT_LOCKED":
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details("Seat is being reserved by another user")
            elif error == "SEAT_UNAVAILABLE":
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Seat is not available")
            return inventory_pb2.ReserveSeatResponse(success=False)

        return inventory_pb2.ReserveSeatResponse(success=True, held_until=held_until or "")

    def ConfirmSeat(self, request, context):
        logger.info(f"ConfirmSeat: seat_id={request.seat_id}, user_id={request.user_id}")
        with get_session() as session:
            success, error = ownership_service.confirm_seat(
                session, request.seat_id, request.user_id
            )

        if not success:
            if error == "SEAT_NOT_FOUND":
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Seat not found")
            elif error == "SEAT_NOT_HELD":
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Seat is not currently held")
            elif error == "NOT_HELD_BY_USER":
                context.set_code(grpc.StatusCode.PERMISSION_DENIED)
                context.set_details("Seat is not held by this user")
            return inventory_pb2.ConfirmSeatResponse(success=False)

        return inventory_pb2.ConfirmSeatResponse(success=True)

    def ReleaseSeat(self, request, context):
        logger.info(f"ReleaseSeat: seat_id={request.seat_id}")
        with get_session() as session:
            success, error = lock_service.release_seat(session, request.seat_id)

        if not success:
            if error == "SEAT_NOT_FOUND":
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Seat not found")
            elif error == "INVALID_STATE":
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Seat cannot be released from current state")
            return inventory_pb2.ReleaseSeatResponse(success=False)

        return inventory_pb2.ReleaseSeatResponse(success=True)

    def UpdateOwner(self, request, context):
        logger.info(f"UpdateOwner: seat_id={request.seat_id}, new_owner_id={request.new_owner_id}")
        with get_session() as session:
            success, error = ownership_service.update_owner(
                session, request.seat_id, request.new_owner_id
            )

        if not success:
            if error == "SEAT_NOT_FOUND":
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Seat not found")
            elif error == "SEAT_NOT_SOLD":
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Seat is not in SOLD state")
            return inventory_pb2.UpdateOwnerResponse(success=False)

        return inventory_pb2.UpdateOwnerResponse(success=True)

    def VerifyTicket(self, request, context):
        logger.info(f"VerifyTicket: seat_id={request.seat_id}")
        with get_session() as session:
            status, owner_user_id, event_id, error = verification_service.verify_ticket(
                session, request.seat_id
            )

        if error:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Seat not found")
            return inventory_pb2.VerifyTicketResponse()

        return inventory_pb2.VerifyTicketResponse(
            status=status or "",
            owner_user_id=owner_user_id or "",
            event_id=event_id or "",
        )

    def MarkCheckedIn(self, request, context):
        logger.info(f"MarkCheckedIn: seat_id={request.seat_id}")
        with get_session() as session:
            success, error = verification_service.mark_checked_in(
                session, request.seat_id
            )

        if not success:
            if error == "SEAT_NOT_FOUND":
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Seat not found")
            elif error == "ALREADY_CHECKED_IN":
                context.set_code(grpc.StatusCode.ALREADY_EXISTS)
                context.set_details("Seat already checked in")
            elif error == "SEAT_NOT_SOLD":
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Seat is not in SOLD state")
            return inventory_pb2.MarkCheckedInResponse(success=False)

        return inventory_pb2.MarkCheckedInResponse(success=True)

    def GetSeatOwner(self, request, context):
        logger.info(f"GetSeatOwner: seat_id={request.seat_id}")
        with get_session() as session:
            owner_user_id, status, error = ownership_service.get_seat_owner(
                session, request.seat_id
            )

        if error:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Seat not found")
            return inventory_pb2.GetSeatOwnerResponse()

        return inventory_pb2.GetSeatOwnerResponse(
            owner_user_id=owner_user_id or "",
            status=status or "",
        )


def create_grpc_server(port=50051):
    """Create and configure the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(
        InventoryServiceServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"gRPC server configured on port {port}")
    return server
