"""
Order Service — Flask application
Handles orders and transfers CRUD.
"""

import os
from flask import Flask, jsonify, request
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

    db.init_app(app)

    # --- Health check ---------------------------------------------------
    @app.route("/health")
    def health():
        return jsonify({
            "status": "healthy",
            "service": "order-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    # --- POST /orders ---------------------------------------------------
    # Called by orchestrator during purchase flow
    # Body: { user_id, seat_id, event_id, credits_charged, status? }
    @app.route("/orders", methods=["POST"])
    def create_order_route():
        data = request.get_json()

        required = ["user_id", "seat_id", "event_id", "credits_charged"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
        
        status = data.get("status", "PENDING")
        if status not in ("PENDING", "CONFIRMED"):
            return jsonify({"error":"status must be 'PENDING' or 'CONFIRMED' on creation"}), 400
        
        order = create_order(
            user_id=data["user_id"],
            seat_id=data["seat_id"],
            event_id=data["event_id"],
            credits_charged=data["credits_charged"],
            status=status,
        )
        return jsonify(order.to_dict()), 201
    
    # --- GET /orders/<order_id> -----------------------------------------
    @app.route("/orders/<order_id>", methods=["GET"])
    def get_order_route(order_id):
        order = get_order_by_id(order_id)
        if not order:
            return jsonify({"error": "Order not found"}), 404
        return jsonify(order.to_dict()), 200

    # --- GET /orders?seat_id= or ?user_id= ------------------------------
    # seat_id: used by Orchestrator for QR verification
    # user_id: used to get user's purchased tickets  
    @app.route("/orders", methods=["GET"])
    def query_orders_route():
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
        
        return jsonify({"error": "Provide seat_id or user_id as query parameter"}), 400
    
    # --- PATCH /orders/<order_id>/status --------------------------------
    # Advances order through its lifecycle
    # PENDING → CONFIRMED (payment success)
    # PENDING → FAILED    (TTL expiry via RabbitMQ DLX)
    # CONFIRMED → REFUNDED
    @app.route("/orders/<order_id>/status", methods=["PATCH"])
    def update_order_status_route(order_id):
        data = request.get_json()
        new_status = data.get("status")

        if not new_status:
            return jsonify({"error": "Missing field: status"}), 400
        
        order, error = update_order_status(order_id, new_status)
        if error:
            status_code = 404 if "not found" in error else 409
            return jsonify({"error": error}), status_code
        
        return jsonify(order.to_dict()), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)
