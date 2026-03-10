import logging
import grpc
from flask import jsonify

from src.utils.http_client import user_service, order_service, event_service
from src.utils.grpc_client import inventory_client

logger = logging.getLogger("orchestrator")

def handle_initiate(initiator_id, seat_id, seller_user_id, buyer_user_id, credits_amount):
    try:
        # Step 1: Verify ownership
        try:
            owner_res = inventory_client.get_seat_owner(seat_id)
            if owner_res.owner_user_id != seller_user_id:
                return jsonify({"success": False, "error_code": "NOT_SEAT_OWNER", "message": "Seller does not own seat"}), 403
            if owner_res.status != "SOLD":
                return jsonify({"success": False, "error_code": "SEAT_UNAVAILABLE", "message": "Seat cannot be transferred"}), 409
        except Exception as e:
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Inventory check failed"}), 500

        # Optional: verify buyer exists and has credits
        # Assuming internal calls handle this, or we fail at confirm

        # Step 2: Create Transfer in Order Service
        t_payload = {
            "seat_id": seat_id,
            "seller_user_id": seller_user_id,
            "buyer_user_id": buyer_user_id,
            "initiated_by": "SELLER" if initiator_id == seller_user_id else "BUYER",
            "credits_amount": credits_amount
        }
        res = order_service.post("/transfers", json=t_payload)
        if res.status_code != 201:
            return jsonify(res.json()), res.status_code
        
        transfer_data = res.json()
        
        # Step 3: Trigger OTPs for both
        user_service.post("/otp/send", json={"user_id": seller_user_id})
        user_service.post("/otp/send", json={"user_id": buyer_user_id})

        return jsonify({
            "success": True,
            "data": {
                "transfer_id": transfer_data["transfer_id"],
                "seat_id": seat_id,
                "status": "PENDING_OTP",
                "message": "Transfer initiated. Both parties will receive an OTP for verification."
            }
        }), 201

    except Exception as e:
        logger.error(f"Initiate transfer error: {str(e)}")
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": str(e)}), 500

def handle_confirm(transfer_id, seller_otp, buyer_otp, user_id):
    try:
        # 1. Get Transfer
        t_res = order_service.get(f"/transfers/{transfer_id}")
        if t_res.status_code != 200:
            return jsonify({"success": False, "error_code": "TRANSFER_NOT_FOUND"}), 404
        transfer = t_res.json()
        
        if transfer["status"] != "PENDING_OTP":
            return jsonify({"success": False, "error_code": "TRANSFER_INVALID_STATE"}), 409

        seller_id = transfer["seller_user_id"]
        buyer_id = transfer["buyer_user_id"]
        credits_amt = transfer["credits_amount"]
        seat_id = transfer["seat_id"]

        from flask import request
        auth_header = request.headers.get("Authorization", "")

        # 2. Verify Seller OTP
        s_otp_res = user_service.post("/otp/verify", json={"user_id": seller_id, "otp_code": seller_otp})
        if s_otp_res.status_code != 200:
            return jsonify({"success": False, "error_code": "OTP_INVALID", "message": "Seller OTP invalid"}), 401

        # 3. Verify Buyer OTP
        b_otp_res = user_service.post("/otp/verify", json={"user_id": buyer_id, "otp_code": buyer_otp})
        if b_otp_res.status_code != 200:
            return jsonify({"success": False, "error_code": "OTP_INVALID", "message": "Buyer OTP invalid"}), 401

        # 4. Transfer Credits (Deduct buyer, Topup seller)
        if credits_amt and credits_amt > 0:
            transfer_res = user_service.post("/credits/transfer", json={
                "from_user_id": buyer_id,
                "to_user_id": seller_id,
                "amount": credits_amt
            }, headers={"Authorization": auth_header})
            if transfer_res.status_code == 402:
                return jsonify({"success": False, "error_code": "INSUFFICIENT_CREDITS", "message": "Not enough credits"}), 402
            if transfer_res.status_code != 200:
                return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Credit transfer failed"}), 500

        # 5. Swap DB Ownership
        try:
            inventory_client.update_owner(seat_id, buyer_id)
        except Exception as e:
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Failed to update ownership"}), 500

        # 6. Update Transfer status to COMPLETED
        order_service.patch(f"/transfers/{transfer_id}/status", json={"status": "COMPLETED"})

        return jsonify({
            "success": True,
            "data": {
                "transfer_id": transfer_id,
                "status": "COMPLETED",
                "seat_id": seat_id,
                "new_owner_user_id": buyer_id,
                "credits_transferred": credits_amt,
                "message": "Transfer complete. Ticket ownership updated."
            }
        }), 200

    except Exception as e:
        logger.error(f"Confirm transfer error: {str(e)}")
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": str(e)}), 500

def handle_dispute(transfer_id, reason, user_id):
    res = order_service.post(f"/transfers/{transfer_id}/dispute", json={"reason": reason})
    return jsonify(res.json()), res.status_code

def handle_reverse(transfer_id, user_id):
    res = order_service.post(f"/transfers/{transfer_id}/reverse")
    if res.status_code != 200:
        return jsonify(res.json()), res.status_code

    transfer = res.json() if isinstance(res.json(), dict) else {}
    seat_id = transfer.get("seat_id")
    seller_user_id = transfer.get("seller_user_id")
    buyer_user_id = transfer.get("buyer_user_id")
    credits_amt = transfer.get("credits_amount") or 0

    if seat_id and seller_user_id:
        try:
            inventory_client.update_owner(seat_id, seller_user_id)
        except Exception:
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Failed to restore ownership"}), 500

    if credits_amt and credits_amt > 0 and seller_user_id and buyer_user_id:
        credit_res = user_service.post("/credits/transfer", json={
            "from_user_id": seller_user_id,
            "to_user_id": buyer_user_id,
            "amount": credits_amt
        })
        if credit_res.status_code != 200:
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Failed to return credits"}), 500

    return jsonify({
        "success": True,
        "data": {
            "transfer_id": transfer_id,
            "status": "REVERSED",
            "seat_id": seat_id,
            "restored_owner_user_id": seller_user_id,
            "credits_returned": credits_amt,
            "message": "Transfer reversed. Ownership and credits restored."
        }
    }), 200
