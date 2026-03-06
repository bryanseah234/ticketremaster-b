"""
Order Service — Flask application
Handles orders and transfers CRUD.
"""

import os
from flask import Flask, jsonify, request
from flasgger import Swagger
from datetime import datetime, timezone
from dotenv import load_dotenv
from db import db
from services.order_service import (
    create_order,
    get_order_by_id,
    get_order_by_seat,
    get_orders_by_user,
    update_order_status,
)
from services.transfer_service import (
    create_transfer,
    get_transfer_by_id,
    get_transfers_by_seat,
    get_transfers_by_user,
    update_transfer_status,
    update_otp_verification,
    dispute_transfer,
    reverse_transfer,
)

load_dotenv()


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://order_svc_user"
        f":{os.getenv('ORDER_DB_PASS')}"
        f"@{os.getenv('ORDER_DB_HOST', 'orders-db')}"
        f":5432"
        f"/orders_db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SWAGGER"] = {"title": "Order Service API", "uiversion": 3}
    Swagger(app)

    db.init_app(app)

    # ── Health check ────────────────────────────────────────────────────────

    @app.route("/health")
    def health():
        return jsonify({
            "status":    "healthy",
            "service":   "order-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ════════════════════════════════════════════════════════════════════════
    # ORDER ROUTES
    # ════════════════════════════════════════════════════════════════════════

    @app.route("/orders", methods=["POST"])
    def create_order_route():
        """
        Create a new order.
        ---
        tags:
          - Orders
        parameters:
          - in: body
            name: body
            required: true
            schema:
              required: [user_id, seat_id, event_id, credits_charged]
              properties:
                user_id:
                  type: string
                  example: a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11
                seat_id:
                  type: string
                  example: b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11
                event_id:
                  type: string
                  example: c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11
                credits_charged:
                  type: number
                  example: 150.00
                status:
                  type: string
                  enum: [PENDING, CONFIRMED]
                  example: PENDING
        responses:
          201:
            description: Order created successfully
          400:
            description: Missing or invalid fields
        """
        data = request.get_json()

        required = ["user_id", "seat_id", "event_id", "credits_charged"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

        status = data.get("status", "PENDING")
        if status not in ("PENDING", "CONFIRMED"):
            return jsonify({"error": "status must be 'PENDING' or 'CONFIRMED' on creation"}), 400

        order = create_order(
            user_id=data["user_id"],
            seat_id=data["seat_id"],
            event_id=data["event_id"],
            credits_charged=data["credits_charged"],
            status=status,
        )
        return jsonify(order.to_dict()), 201

    @app.route("/orders/<order_id>", methods=["GET"])
    def get_order_route(order_id):
        """
        Get an order by ID.
        ---
        tags:
          - Orders
        parameters:
          - in: path
            name: order_id
            type: string
            required: true
        responses:
          200:
            description: Order found
          404:
            description: Order not found
        """
        order = get_order_by_id(order_id)
        if not order:
            return jsonify({"error": "Order not found"}), 404
        return jsonify(order.to_dict()), 200

    @app.route("/orders", methods=["GET"])
    def query_orders_route():
        """
        Query orders by seat_id or user_id.
        ---
        tags:
          - Orders
        parameters:
          - in: query
            name: seat_id
            type: string
            description: Used by Orchestrator in Scenario 3 (QR verification)
          - in: query
            name: user_id
            type: string
            description: Returns all orders for a user (Purchased Tickets view)
        responses:
          200:
            description: Orders found
          400:
            description: No query parameter provided
          404:
            description: No order found
        """
        seat_id = request.args.get("seat_id")
        user_id = request.args.get("user_id")

        if seat_id:
            order = get_order_by_seat(seat_id)
            if not order:
                return jsonify({"error": "No order found for this seat"}), 404
            return jsonify(order.to_dict()), 200

        if user_id:
            orders = get_orders_by_user(user_id)
            return jsonify([o.to_dict() for o in orders]), 200

        return jsonify({"error": "Provide seat_id or user_id as a query parameter"}), 400

    @app.route("/orders/<order_id>/status", methods=["PATCH"])
    def update_order_status_route(order_id):
        """
        Update order status.
        ---
        tags:
          - Orders
        parameters:
          - in: path
            name: order_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              required: [status]
              properties:
                status:
                  type: string
                  enum: [CONFIRMED, FAILED, REFUNDED]
                  example: CONFIRMED
        responses:
          200:
            description: Status updated
          404:
            description: Order not found
          409:
            description: Invalid status transition
        """
        data = request.get_json()
        new_status = data.get("status")

        if not new_status:
            return jsonify({"error": "Missing field: status"}), 400

        order, error = update_order_status(order_id, new_status)
        if error:
            status_code = 404 if "not found" in error else 409
            return jsonify({"error": error}), status_code

        return jsonify(order.to_dict()), 200

    # ════════════════════════════════════════════════════════════════════════
    # TRANSFER ROUTES
    # ════════════════════════════════════════════════════════════════════════

    @app.route("/transfers", methods=["POST"])
    def create_transfer_route():
        """
        Create a new transfer.
        ---
        tags:
          - Transfers
        parameters:
          - in: body
            name: body
            required: true
            schema:
              required: [seat_id, seller_user_id, buyer_user_id, initiated_by]
              properties:
                seat_id:
                  type: string
                  example: b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11
                seller_user_id:
                  type: string
                  example: a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11
                buyer_user_id:
                  type: string
                  example: d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11
                initiated_by:
                  type: string
                  enum: [SELLER, BUYER]
                  example: BUYER
                credits_amount:
                  type: number
                  example: 150.00
        responses:
          201:
            description: Transfer created
          400:
            description: Missing or invalid fields
        """
        data = request.get_json()

        required = ["seat_id", "seller_user_id", "buyer_user_id", "initiated_by"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

        if data["initiated_by"] not in ("SELLER", "BUYER"):
            return jsonify({"error": "initiated_by must be 'SELLER' or 'BUYER'"}), 400

        transfer = create_transfer(
            seat_id=data["seat_id"],
            seller_user_id=data["seller_user_id"],
            buyer_user_id=data["buyer_user_id"],
            initiated_by=data["initiated_by"],
            credits_amount=data.get("credits_amount"),
        )
        return jsonify(transfer.to_dict()), 201

    @app.route("/transfers/<transfer_id>", methods=["GET"])
    def get_transfer_route(transfer_id):
        """
        Get a transfer by ID.
        ---
        tags:
          - Transfers
        parameters:
          - in: path
            name: transfer_id
            type: string
            required: true
        responses:
          200:
            description: Transfer found
          404:
            description: Transfer not found
        """
        transfer = get_transfer_by_id(transfer_id)
        if not transfer:
            return jsonify({"error": "Transfer not found"}), 404
        return jsonify(transfer.to_dict()), 200

    @app.route("/transfers", methods=["GET"])
    def query_transfers_route():
        """
        Query transfers by seat_id or user_id.
        ---
        tags:
          - Transfers
        parameters:
          - in: query
            name: seat_id
            type: string
          - in: query
            name: user_id
            type: string
            description: Returns transfers where user is buyer or seller
        responses:
          200:
            description: Transfers found
          400:
            description: No query parameter provided
        """
        seat_id = request.args.get("seat_id")
        user_id = request.args.get("user_id")

        if seat_id:
            transfers = get_transfers_by_seat(seat_id)
            return jsonify([t.to_dict() for t in transfers]), 200

        if user_id:
            transfers = get_transfers_by_user(user_id)
            return jsonify([t.to_dict() for t in transfers]), 200

        return jsonify({"error": "Provide seat_id or user_id as a query parameter"}), 400

    @app.route("/transfers/<transfer_id>/status", methods=["PATCH"])
    def update_transfer_status_route(transfer_id):
        """
        Update transfer status.
        ---
        tags:
          - Transfers
        parameters:
          - in: path
            name: transfer_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              required: [status]
              properties:
                status:
                  type: string
                  enum: [PENDING_OTP, COMPLETED, DISPUTED, FAILED]
                  example: PENDING_OTP
        responses:
          200:
            description: Status updated
          404:
            description: Transfer not found
          409:
            description: Invalid status transition
        """
        data = request.get_json()
        new_status = data.get("status")

        if not new_status:
            return jsonify({"error": "Missing field: status"}), 400

        transfer, error = update_transfer_status(transfer_id, new_status)
        if error:
            status_code = 404 if "not found" in error else 409
            return jsonify({"error": error}), status_code

        return jsonify(transfer.to_dict()), 200

    @app.route("/transfers/<transfer_id>/otp", methods=["PATCH"])
    def update_otp_route(transfer_id):
        """
        Update OTP verification status for seller or buyer.
        ---
        tags:
          - Transfers
        parameters:
          - in: path
            name: transfer_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              required: [party, verified]
              properties:
                party:
                  type: string
                  enum: [seller, buyer]
                  example: seller
                verified:
                  type: boolean
                  example: true
                verification_sid:
                  type: string
                  example: VE1234567890abcdef
        responses:
          200:
            description: OTP status updated
          400:
            description: Missing or invalid fields
          404:
            description: Transfer not found
        """
        data = request.get_json()
        party = data.get("party")
        verified = data.get("verified")

        if party is None or verified is None:
            return jsonify({"error": "Missing fields: party and verified are required"}), 400

        transfer, error = update_otp_verification(
            transfer_id=transfer_id,
            party=party,
            verified=verified,
            verification_sid=data.get("verification_sid"),
        )
        if error:
            status_code = 404 if "not found" in error else 400
            return jsonify({"error": error}), status_code

        return jsonify(transfer.to_dict()), 200

    @app.route("/transfers/<transfer_id>/dispute", methods=["POST"])
    def dispute_transfer_route(transfer_id):
        """
        Raise a dispute on a transfer.
        ---
        tags:
          - Transfers
        parameters:
          - in: path
            name: transfer_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              required: [reason]
              properties:
                reason:
                  type: string
                  example: Suspected phishing attempt
        responses:
          200:
            description: Transfer disputed
          404:
            description: Transfer not found
          409:
            description: Transfer cannot be disputed in current status
        """
        data = request.get_json()
        reason = data.get("reason")

        if not reason:
            return jsonify({"error": "Missing field: reason"}), 400

        transfer, error = dispute_transfer(transfer_id, reason)
        if error:
            status_code = 404 if "not found" in error else 409
            return jsonify({"error": error}), status_code

        return jsonify(transfer.to_dict()), 200

    @app.route("/transfers/<transfer_id>/reverse", methods=["POST"])
    def reverse_transfer_route(transfer_id):
        """
        Reverse a completed or disputed transfer.
        ---
        tags:
          - Transfers
        description: >
          Only updates the Order Service record.
          The Orchestrator is responsible for reversing credits
          and calling Inventory gRPC UpdateOwner back to seller.
        parameters:
          - in: path
            name: transfer_id
            type: string
            required: true
        responses:
          200:
            description: Transfer reversed
          404:
            description: Transfer not found
          409:
            description: Transfer cannot be reversed in current status
        """
        transfer, error = reverse_transfer(transfer_id)
        if error:
            status_code = 404 if "not found" in error else 409
            return jsonify({"error": error}), status_code

        return jsonify(transfer.to_dict()), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)