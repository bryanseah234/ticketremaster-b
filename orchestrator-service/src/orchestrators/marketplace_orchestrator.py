"""
Marketplace Orchestrator — Orchestrator Service
Coordinates listing and purchasing of tickets on the resale marketplace.
"""

import logging
from flask import jsonify, request
from src.utils.http_client import user_service, order_service, event_service
from src.utils.grpc_client import inventory_client

logger = logging.getLogger("orchestrator")

def handle_list_ticket(seat_id, seller_user_id, asking_price):
    try:
        # Step 1: Verify Ownership & Status via Inventory gRPC
        try:
            owner_res = inventory_client.get_seat_owner(seat_id)
            if owner_res.owner_user_id != seller_user_id:
                return jsonify({"success": False, "error_code": "NOT_SEAT_OWNER", "message": "You do not own this seat"}), 403
            if owner_res.status != "SOLD":
                return jsonify({"success": False, "error_code": "INVALID_SEAT_STATUS", "message": f"Seat is {owner_res.status}, must be SOLD to list."}), 400
        except Exception as e:
            logger.error(f"Inventory check failed: {e}")
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Failed to verify seat ownership"}), 500

        # Step 2: Create listing in Order Service
        listing_payload = {
            "seat_id": seat_id,
            "seller_user_id": seller_user_id,
            "asking_price": asking_price
        }
        listing_res = order_service.post("/marketplace/listings", json=listing_payload)
        if listing_res.status_code != 201:
            return jsonify(listing_res.json()), listing_res.status_code
        
        listing_data = listing_res.json()
        listing_id = listing_data["listing_id"]

        # Step 3: Update seat status to LISTED in Inventory Service
        try:
            list_res = inventory_client.list_seat(seat_id, seller_user_id)
            if not list_res.success:
                order_service.patch(f"/marketplace/listings/{listing_id}/status", json={"status": "CANCELLED"})
                return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Failed to mark seat as listed"}), 500
        except Exception as e:
            logger.error(f"gRPC ListSeat failed: {e}")
            order_service.patch(f"/marketplace/listings/{listing_id}/status", json={"status": "CANCELLED"})
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Inventory update failed"}), 500

        return jsonify({
            "success": True,
            "data": {
                "listing_id": listing_id,
                "seat_id": seat_id,
                "status": "LISTED",
                "message": "Ticket successfully listed on the marketplace."
            }
        }), 201

    except Exception as e:
        logger.error(f"List ticket error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": str(e)}), 500

def handle_buy_listing(listing_id, buyer_user_id):
    try:
        # Step 1: Fetch Listing details
        res = order_service.get(f"/marketplace/listings/{listing_id}")
        if res.status_code != 200:
            return jsonify({"success": False, "error_code": "LISTING_NOT_FOUND"}), 404
        
        listing = res.json()
        if listing["status"] != "ACTIVE":
            return jsonify({"success": False, "error_code": "LISTING_UNAVAILABLE", "message": "Listing is no longer active"}), 400
        
        seat_id = listing["seat_id"]
        seller_id = listing["seller_user_id"]
        price = listing["asking_price"]

        if str(seller_id) == str(buyer_user_id):
            return jsonify({"success": False, "error_code": "INVALID_PURCHASE", "message": "You cannot buy your own listing"}), 400

        # Step 2: Internal Escrow — Hold credits from buyer
        auth_header = request.headers.get("Authorization", "")
        hold_payload = {
            "user_id": buyer_user_id,
            "amount": price,
            "reference_id": listing_id,
            "description": f"Marketplace purchase for seat {seat_id}"
        }
        hold_res = user_service.post("/credits/escrow/hold", json=hold_payload, headers={"Authorization": auth_header})
        
        if hold_res.status_code != 200:
            return jsonify(hold_res.json()), hold_res.status_code
        
        transaction_id = hold_res.json().get("transaction_id")

        # Step 3: Update listing status to PENDING_TRANSFER in Order Service
        order_service.patch(f"/marketplace/listings/{listing_id}/status", json={
            "status": "PENDING_TRANSFER",
            "buyer_user_id": buyer_user_id,
            "transaction_id": transaction_id
        })

        # Step 4: Hold seat in Inventory Service (Status: HELD)
        try:
            inventory_client.reserve_seat(seat_id, buyer_user_id)
        except Exception as e:
            logger.error(f"Failed to hold seat for transfer: {e}")
            order_service.patch(f"/marketplace/listings/{listing_id}/status", json={"status": "ACTIVE"})
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Failed to secure ticket"}), 500

        # Step 5: Notify Seller
        user_service.post("/otp/send", json={"user_id": seller_id}, headers={"Authorization": auth_header})

        return jsonify({
            "success": True,
            "data": {
                "listing_id": listing_id,
                "status": "PENDING_APPROVAL",
                "message": "Payment secure in escrow. Waiting for seller to approve."
            }
        }), 200

    except Exception as e:
        logger.error(f"Buy listing error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": str(e)}), 500

def handle_approve_listing(listing_id, seller_user_id, seller_otp):
    try:
        # Step 1: Verify OTP
        auth_header = request.headers.get("Authorization", "")
        otp_res = user_service.post("/otp/verify", json={"user_id": seller_user_id, "otp_code": seller_otp}, headers={"Authorization": auth_header})
        if otp_res.status_code != 200:
            return jsonify({"success": False, "error_code": "OTP_INVALID", "message": "Invalid OTP"}), 401

        # Step 2: Fetch Listing
        res = order_service.get(f"/marketplace/listings/{listing_id}")
        if res.status_code != 200:
            return jsonify({"success": False, "error_code": "LISTING_NOT_FOUND"}), 404
        listing = res.json()
        
        seat_id = listing["seat_id"]
        transaction_id = listing["escrow_transaction_id"]
        buyer_id = listing["buyer_user_id"]

        # Step 3: Ownership Change (gRPC)
        try:
            inventory_client.confirm_seat(seat_id, buyer_id)
        except Exception as e:
            logger.error(f"Failed to confirm seat for buyer: {e}")
            return jsonify({"success": False, "error_code": "INTERNAL_ERROR", "message": "Ownership transfer failed"}), 500

        # Step 4: Release Escrow to Seller
        release_res = user_service.post("/credits/escrow/release", json={
            "transaction_id": transaction_id,
            "seller_user_id": seller_user_id
        }, headers={"Authorization": auth_header})
        
        if release_res.status_code != 200:
            logger.error(f"Critical error: Escrow release failed after ownership change!")
            return jsonify({"success": False, "error_code": "SETTLEMENT_ERROR", "message": "Ownership transferred but credit settlement failed. Admin audit required."}), 500

        # Step 5: Mark Listing Complete
        order_service.patch(f"/marketplace/listings/{listing_id}/status", json={"status": "COMPLETED"})

        return jsonify({
            "success": True,
            "data": {
                "listing_id": listing_id,
                "status": "COMPLETED",
                "message": "Ticket resale completed successfully. Credits transferred to seller."
            }
        }), 200

    except Exception as e:
        logger.error(f"Approve listing error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR"}), 500
