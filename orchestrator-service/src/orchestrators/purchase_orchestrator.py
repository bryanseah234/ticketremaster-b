import logging
from datetime import datetime, timezone
import grpc
from flask import jsonify

from src.utils.http_client import user_service, order_service, event_service
from src.utils.grpc_client import inventory_client
from src.utils.rabbitmq_client import publish_seat_hold_ttl

logger = logging.getLogger("orchestrator")

def handle_reserve(seat_id, user_id, event_id=None):
    try:
        if not event_id:
            return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "event_id required"}), 400

        # Step 1: Fetch seat price from Event Service
        res = event_service.get(f"/api/events/{event_id}")
        if res.status_code != 200:
            return jsonify({"success": False, "error_code": "EVENT_NOT_FOUND", "message": "Event not found"}), 404
        
        event_data = res.json().get("data", {})
        seats = event_data.get("seats", [])
        pricing = event_data.get("pricing_tiers", {})
        
        seat_found = False
        seat_price = pricing.get("CAT1", 150) # Default to CAT1 price or 150
        
        for s in seats:
            if s.get("seat_id") == seat_id:
                seat_found = True
                # If the seat somehow has a specific price, use it, otherwise fallback
                if s.get("price"):
                    seat_price = s.get("price")
                break
                
        if not seat_found:
            return jsonify({"success": False, "error_code": "SEAT_NOT_FOUND", "message": "Seat not found in event"}), 404

        # Step 2: Reserve seat via gRPC (Inventory Service)
        try:
            reserve_res = inventory_client.reserve_seat(seat_id, user_id)
            if not reserve_res.success:
                return jsonify({"success": False, "error_code": "SEAT_UNAVAILABLE", "message": "Seat is not available"}), 409
            held_until = reserve_res.held_until
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.ALREADY_EXISTS:
                return jsonify({"success": False, "error_code": "SEAT_ALREADY_SOLD", "message": "Seat already sold"}), 409
            return jsonify({"success": False, "error_code": "SEAT_UNAVAILABLE", "message": "Wait lock failed"}), 409
            
        # Step 3: Create PENDING order
        order_payload = {
            "user_id": user_id,
            "seat_id": seat_id,
            "event_id": event_id,
            "credits_charged": seat_price,
            "status": "PENDING"
        }
        order_res = order_service.post("/orders", json=order_payload)
        if order_res.status_code != 201:
            inventory_client.release_seat(seat_id)
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Could not create order"}), 500
            
        order_data = order_res.json()
        order_id = order_data["order_id"]
        
        # Step 4: Publish TTL to RabbitMQ
        reserved_at = datetime.now(timezone.utc).isoformat()
        publish_seat_hold_ttl(seat_id, user_id, order_id, reserved_at)
        
        return jsonify({
            "success": True,
            "data": {
                "order_id": order_id,
                "seat_id": seat_id,
                "status": "HELD",
                "held_until": held_until,
                "ttl_seconds": 300,
                "message": "Seat reserved. Complete payment within 5 minutes."
            }
        }), 200

    except Exception as e:
        logger.error(f"Reserve error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": str(e)}), 500

def handle_pay(order_id, user_id):
    try:
        # Step 1: Fetch order
        ord_res = order_service.get(f"/orders/{order_id}")
        if ord_res.status_code == 404:
            return jsonify({"success": False, "error_code": "ORDER_NOT_FOUND", "message": "Order not found"}), 404
        order_data = ord_res.json()
        
        if order_data.get("status") == "CONFIRMED":
            return jsonify({"success": False, "error_code": "ORDER_ALREADY_CONFIRMED", "message": "Already paid"}), 409
            
        if order_data.get("user_id") != user_id:
            return jsonify({"success": False, "error_code": "FORBIDDEN", "message": "Not your order"}), 403
            
        seat_id = order_data.get("seat_id")
        price = order_data.get("credits_charged")
        
        # Step 2: Check Inventory status to ensure it's still HELD by this user
        try:
            owner_res = inventory_client.get_seat_owner(seat_id)
            if owner_res.status != "HELD" or owner_res.owner_user_id != user_id:
                return jsonify({"success": False, "error_code": "HOLD_EXPIRED", "message": "Seat hold expired"}), 410
        except Exception:
            return jsonify({"success": False, "error_code": "INITIALIZATION_ERROR", "message": "Inventory check failed"}), 500

        # Step 3: Deduct credits (User Service)
        pass_headers = {"Authorization": f"Bearer {order_id}"} # Optional info
        deduct_res = user_service.post("/api/credits/deduct", json={"amount": price}, headers={"X-User-Id": user_id})
        # Wait, user_service might expect Bearer token via JWT. We should send the JWT down or just internal bypass?
        # Actually user_service/deduct route probably takes JWT.
        # But wait! Orchestrator doesn't have the original JWT? `request.headers.get("Authorization")` could be used!
        from flask import request
        auth_header = request.headers.get("Authorization", "")
        deduct_res = user_service.post("/api/credits/deduct", json={"amount": price}, headers={"Authorization": auth_header})
        
        if deduct_res.status_code == 402:
            return jsonify({"success": False, "error_code": "INSUFFICIENT_CREDITS", "message": "Not enough credits"}), 402
        if deduct_res.status_code == 428:
            return jsonify({"success": False, "error_code": "OTP_REQUIRED", "message": "OTP verification required"}), 428
        if deduct_res.status_code != 200:
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": f"Deduct failed: {deduct_res.text}"}), 500
            
        new_balance = deduct_res.json().get("data", {}).get("remaining_balance", 0)

        # Step 4: Confirm Order (Order Service)
        upd_res = order_service.patch(f"/orders/{order_id}/status", json={"status": "CONFIRMED"})
        if upd_res.status_code != 200:
            user_service.post("/api/credits/refund", json={"amount": price, "reason": "Order update failed"}, headers={"Authorization": auth_header})
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Failed to update order"}), 500
            
        # Step 5: Confirm Seat (Inventory Service)
        try:
            conf_res = inventory_client.confirm_seat(seat_id, user_id)
            if not conf_res.success:
                raise Exception("gRPC confirm_seat returned success=False")
        except Exception as e:
            user_service.post("/api/credits/refund", json={"amount": price, "reason": "Seat confirm failed"}, headers={"Authorization": auth_header})
            order_service.patch(f"/orders/{order_id}/status", json={"status": "FAILED"})
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Failed to confirm seat"}), 500

        return jsonify({
            "success": True,
            "data": {
                "order_id": order_id,
                "seat_id": seat_id,
                "status": "CONFIRMED",
                "credits_charged": price,
                "remaining_balance": new_balance,
                "message": "Purchase confirmed! Your ticket is ready."
            }
        }), 200

    except Exception as e:
        logger.error(f"Pay error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": str(e)}), 500

def handle_verify_otp(user_id, otp_code, context, reference_id):
    try:
        from flask import request
        auth_header = request.headers.get("Authorization", "")
        res = user_service.post("/otp/verify", json={
            "user_id": user_id,
            "otp_code": otp_code,
            "context": context,
            "reference_id": reference_id
        }, headers={"Authorization": auth_header})
        return jsonify(res.json()), res.status_code
    except Exception as e:
        logger.error(f"OTP Error: {str(e)}")
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR"}), 500
