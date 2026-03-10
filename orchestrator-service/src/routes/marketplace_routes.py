from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

logger = logging.getLogger("orchestrator")
marketplace_bp = Blueprint('marketplace', __name__)

@marketplace_bp.route('/marketplace/list', methods=['POST'])
@jwt_required()
def list_ticket():
    from src.orchestrators.marketplace_orchestrator import handle_list_ticket
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    seat_id = data.get('seat_id')
    asking_price = data.get('asking_price')

    if not seat_id or asking_price is None:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "seat_id and asking_price are required"}), 400

    return handle_list_ticket(seat_id, user_id, asking_price)

@marketplace_bp.route('/marketplace/listings', methods=['GET'])
@jwt_required()
def get_listings():
    from src.utils.http_client import order_service, event_service, inventory_service_http
    from src.utils.grpc_client import inventory_client
    status = request.args.get('status', 'ACTIVE')
    res = order_service.get(f"/marketplace/listings?status={status}")
    if res.status_code != 200:
        return jsonify(res.json()), res.status_code

    listings = res.json()
    if not isinstance(listings, list):
        return jsonify(listings), res.status_code

    event_cache = {}
    seat_cache = {}
    enriched = []

    for listing in listings:
        listing_data = dict(listing)
        seat_id = listing.get("seat_id")
        event_id = None
        seat_info = None

        if seat_id:
            try:
                seat_res = inventory_client.verify_ticket(seat_id)
                event_id = seat_res.event_id or None
            except Exception:
                event_id = None

        if event_id:
            if event_id not in seat_cache:
                seat_cache[event_id] = {}
                try:
                    seats_res = inventory_service_http.get("/internal/seats", params={"event_id": event_id})
                    if seats_res.status_code == 200:
                        seats_data = seats_res.json().get("data", [])
                        seat_cache[event_id] = {
                            seat.get("seat_id"): seat for seat in seats_data if seat.get("seat_id")
                        }
                except Exception:
                    seat_cache[event_id] = {}

            seat_info = seat_cache.get(event_id, {}).get(seat_id)

            if event_id not in event_cache:
                try:
                    event_res = event_service.get(f"/api/events/{event_id}")
                    if event_res.status_code == 200:
                        event_body = event_res.json()
                        event_cache[event_id] = event_body.get("data") if isinstance(event_body, dict) else None
                    else:
                        event_cache[event_id] = None
                except Exception:
                    event_cache[event_id] = None

        event_data = event_cache.get(event_id) if event_id else None
        listing_data["event"] = {
            "event_id": event_id,
            "name": event_data.get("name") if event_data else None,
            "event_date": event_data.get("event_date") if event_data else None,
            "venue": event_data.get("venue") if event_data else None,
            "hall_id": event_data.get("hall_id") if event_data else None,
        } if event_id else None
        listing_data["seat"] = {
            "seat_id": seat_id,
            "row_number": seat_info.get("row_number") if seat_info else None,
            "seat_number": seat_info.get("seat_number") if seat_info else None,
            "status": seat_info.get("status") if seat_info else None,
        }
        enriched.append(listing_data)

    return jsonify(enriched), res.status_code

@marketplace_bp.route('/marketplace/buy', methods=['POST'])
@jwt_required()
def buy_listing():
    from src.orchestrators.marketplace_orchestrator import handle_buy_listing
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    listing_id = data.get('listing_id')

    if not listing_id:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "listing_id is required"}), 400

    return handle_buy_listing(listing_id, user_id)

@marketplace_bp.route('/marketplace/approve', methods=['POST'])
@jwt_required()
def approve_listing():
    from src.orchestrators.marketplace_orchestrator import handle_approve_listing
    data = request.get_json() or {}
    user_id = get_jwt_identity()
    listing_id = data.get('listing_id')
    otp_code = data.get('otp_code')

    if not listing_id or not otp_code:
        return jsonify({"success": False, "error_code": "VALIDATION_ERROR", "message": "listing_id and otp_code are required"}), 400

    return handle_approve_listing(listing_id, user_id, otp_code)
