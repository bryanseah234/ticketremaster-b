import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any
import uuid

import redis

from app import create_app, db
from models import SeatInventory
from seat_inventory_pb2 import (
    GetSeatStatusResponse,
    HoldSeatResponse,
    ReleaseSeatResponse,
    SellSeatResponse,
)
from seat_inventory_pb2_grpc import SeatInventoryServiceServicer

logger = logging.getLogger(__name__)


def _get_redis_client():
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    try:
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable for seat hold caching: %s", exc)
        return None


def _write_hold_cache(
    inventory_id: str,
    user_id: str,
    hold_token: str,
    held_until_iso: str,
    ttl_seconds: int,
) -> None:
    client = _get_redis_client()
    if client is None:
        return
    payload: dict[str, Any] = {
        "status": "held",
        "heldByUserId": user_id,
        "holdToken": hold_token,
        "heldUntil": held_until_iso,
    }
    try:
        client.setex(f"hold:{inventory_id}", ttl_seconds, json.dumps(payload))
    except Exception as exc:
        logger.warning("Redis hold cache write failed for %s: %s", inventory_id, exc)


def _delete_hold_cache(inventory_id: str) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.delete(f"hold:{inventory_id}")
    except Exception as exc:
        logger.warning("Redis hold cache delete failed for %s: %s", inventory_id, exc)


class SeatInventoryGrpcService(SeatInventoryServiceServicer):
    def __init__(self, flask_app=None):
        self.app = flask_app or create_app()

    def HoldSeat(self, request, context):
        with self.app.app_context():
            now = datetime.now(UTC)
            hold_seconds = request.hold_duration_seconds if request.hold_duration_seconds > 0 else 300
            held_until = now + timedelta(seconds=hold_seconds)
            hold_token = str(uuid.uuid4())

            locked_row = (
                db.session.query(SeatInventory)
                .filter(SeatInventory.inventoryId == request.inventory_id)
                .with_for_update()
                .one_or_none()
            )

            if not locked_row:
                db.session.rollback()
                return HoldSeatResponse(
                    success=False,
                    status='not_found',
                    held_until='',
                    error_code='INVENTORY_NOT_FOUND',
                    hold_token='',
                )

            if locked_row.status != 'available':
                db.session.rollback()
                return HoldSeatResponse(
                    success=False,
                    status=locked_row.status,
                    held_until=locked_row.heldUntil.isoformat() if locked_row.heldUntil else '',
                    error_code='SEAT_NOT_AVAILABLE',
                    hold_token='',
                )

            updated_rows = (
                db.session.query(SeatInventory)
                .filter(
                    SeatInventory.inventoryId == request.inventory_id,
                    SeatInventory.status == 'available',
                )
                .update(
                    {
                        SeatInventory.status: 'held',
                        SeatInventory.heldByUserId: request.user_id,
                        SeatInventory.holdToken: hold_token,
                        SeatInventory.heldUntil: held_until,
                    },
                    synchronize_session=False,
                )
            )

            if updated_rows != 1:
                db.session.rollback()
                latest = db.session.get(SeatInventory, request.inventory_id)
                return HoldSeatResponse(
                    success=False,
                    status=latest.status if latest else 'not_found',
                    held_until=latest.heldUntil.isoformat() if latest and latest.heldUntil else '',
                    error_code='SEAT_NOT_AVAILABLE',
                    hold_token='',
                )

            db.session.commit()
            _write_hold_cache(
                inventory_id=request.inventory_id,
                user_id=request.user_id,
                hold_token=hold_token,
                held_until_iso=held_until.isoformat(),
                ttl_seconds=hold_seconds,
            )
            return HoldSeatResponse(
                success=True,
                status='held',
                held_until=held_until.isoformat(),
                error_code='',
                hold_token=hold_token,
            )

    def ReleaseSeat(self, request, context):
        with self.app.app_context():
            inventory = (
                db.session.query(SeatInventory)
                .filter(SeatInventory.inventoryId == request.inventory_id)
                .with_for_update()
                .one_or_none()
            )

            if (
                not inventory
                or inventory.status != 'held'
                or inventory.heldByUserId != request.user_id
                or inventory.holdToken != request.hold_token
            ):
                db.session.rollback()
                return ReleaseSeatResponse(success=False)

            inventory.status = 'available'
            inventory.heldByUserId = None
            inventory.holdToken = None
            inventory.heldUntil = None
            db.session.commit()
            _delete_hold_cache(request.inventory_id)
            return ReleaseSeatResponse(success=True)

    def SellSeat(self, request, context):
        with self.app.app_context():
            inventory = (
                db.session.query(SeatInventory)
                .filter(SeatInventory.inventoryId == request.inventory_id)
                .with_for_update()
                .one_or_none()
            )

            if not inventory:
                db.session.rollback()
                return SellSeatResponse(success=False)

            if (
                inventory.status != 'held'
                or inventory.heldByUserId != request.user_id
                or inventory.holdToken != request.hold_token
            ):
                db.session.rollback()
                return SellSeatResponse(success=False)

            inventory.status = 'sold'
            inventory.heldByUserId = None
            inventory.holdToken = None
            inventory.heldUntil = None
            db.session.commit()
            _delete_hold_cache(request.inventory_id)
            return SellSeatResponse(success=True)

    def GetSeatStatus(self, request, context):
        with self.app.app_context():
            inventory = db.session.get(SeatInventory, request.inventory_id)
            if not inventory:
                return GetSeatStatusResponse(inventory_id=request.inventory_id, status='not_found', held_until='')

            return GetSeatStatusResponse(
                inventory_id=inventory.inventoryId,
                status=inventory.status,
                held_until=inventory.heldUntil.isoformat() if inventory.heldUntil else '',
            )
