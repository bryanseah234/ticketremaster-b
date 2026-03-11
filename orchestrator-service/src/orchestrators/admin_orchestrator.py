import os
import requests
import grpc
import logging
from flask import jsonify
from src import inventory_pb2, inventory_pb2_grpc

logger = logging.getLogger("orchestrator")

EVENT_SERVICE_URL = os.environ.get("EVENT_SERVICE_URL", "http://event-service:5002")
INVENTORY_SERVICE_URL = os.environ.get("INVENTORY_SERVICE_URL", "inventory-service:50051")

def handle_create_event(data):
    print(f"DEBUG: Entering handle_create_event with data: {data}")
    # Step 1: Create Event via Event Service
    try:
        print(f"DEBUG: Calling Event Service at {EVENT_SERVICE_URL}/api/events")
        response = requests.post(f"{EVENT_SERVICE_URL}/api/events", json=data, timeout=5.0)
        print(f"DEBUG: Event Service status_code: {response.status_code}")
        if response.status_code != 201 and response.status_code != 200:
            print(f"DEBUG: Event Service error: {response.text}")
            return jsonify({
                "success": False, 
                "error_code": "EVENT_SERVICE_ERROR", 
                "message": f"Event Service returned {response.status_code}: {response.text}"
            }), 502
            
        json_resp = response.json()
        print(f"DEBUG: Event Service JSON response: {json_resp}")
        event_dict = json_resp.get('data', {})
        event_id = event_dict.get('event_id')
        total_seats = data.get('total_seats')
        
        print(f"DEBUG: Extracted event_id: {event_id}, total_seats: {total_seats}")
    except Exception as e:
        print(f"DEBUG: Exception in Step 1: {str(e)}")
        logger.error(f"Error calling Event service: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error_code": "SERVICE_UNAVAILABLE",
            "message": f"Event service interaction failed: {str(e)}"
        }), 503

    # Step 2: Provision seats in Inventory gRPC
    try:
        print(f"DEBUG: Calling Inventory Service gRPC at {INVENTORY_SERVICE_URL}")
        with grpc.insecure_channel(INVENTORY_SERVICE_URL) as channel:
            stub = inventory_pb2_grpc.InventoryServiceStub(channel)
            req = inventory_pb2.CreateSeatsRequest(
                event_id=str(event_id),
                total_seats=int(total_seats)
            )
            print(f"DEBUG: Sending CreateSeatsRequest: event_id={req.event_id}, total_seats={req.total_seats}")
            resp = stub.CreateSeats(req, timeout=10.0)
            print(f"DEBUG: Inventory Service gRPC response: success={resp.success}, seats_created={resp.seats_created}")
            
            if not resp.success:
                logger.error("Failed to create seats in Inventory Service")
                return jsonify({
                    "success": False,
                    "error_code": "INVENTORY_SERVICE_ERROR",
                    "message": "Failed to provision seats."
                }), 502
                
            event_dict['seats_created'] = resp.seats_created
    except Exception as e:
        print(f"DEBUG: Exception in Step 2: {str(e)}")
        logger.error(f"gRPC error calling Inventory Service: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error_code": "SERVICE_UNAVAILABLE",
            "message": f"Inventory service interaction failed: {str(e)}"
        }), 503

    print("DEBUG: handle_create_event succeeded")
    return jsonify({"success": True, "data": event_dict}), 201

def handle_get_dashboard(event_id):
    # Step 1: Fetch Event Details
    try:
        event_resp = requests.get(f"{EVENT_SERVICE_URL}/api/events/{event_id}", timeout=5.0)
        if event_resp.status_code != 200:
             return jsonify({
                "success": False, 
                "error_code": "EVENT_NOT_FOUND", 
                "message": "Event not found"
            }), 404
        event_data = event_resp.json().get('data', {})
    except requests.RequestException as e:
        return jsonify({"success": False, "error_code": "SERVICE_UNAVAILABLE", "message": "Event service is unavailable"}), 503

    # Step 2: Fetch Event Seats Info from Inventory Service via gRPC
    seats_list = []
    try:
        with grpc.insecure_channel(INVENTORY_SERVICE_URL) as channel:
            stub = inventory_pb2_grpc.InventoryServiceStub(channel)
            req = inventory_pb2.GetEventSeatsInfoRequest(event_id=event_id)
            resp = stub.GetEventSeatsInfo(req, timeout=10.0)
            for s in resp.seats:
                seats_list.append({
                    "seat_id": s.seat_id,
                    "row_number": s.row_number,
                    "seat_number": s.seat_number,
                    "status": s.status,
                    "owner_user_id": s.owner_user_id
                })
    except grpc.RpcError as e:
        logger.error(f"gRPC error calling Inventory Service: {e}")
        return jsonify({"success": False, "error_code": "SERVICE_UNAVAILABLE", "message": "Inventory service is unavailable"}), 503

    # Formulate Dashboard Response to match API.md
    sold_seats = len([s for s in seats_list if s['status'] in ['SOLD', 'CHECKED_IN']])
    held_seats = len([s for s in seats_list if s['status'] == 'HELD'])
    available_seats = len([s for s in seats_list if s['status'] == 'AVAILABLE'])
    
    dashboard_data = {
        "event_id": event_id,
        "name": event_data.get('name'),
        "event_date": event_data.get('event_date'),
        "stats": {
            "total_seats": len(seats_list),
            "seats_sold": sold_seats,
            "seats_held": held_seats,
            "seats_available": available_seats,
            "total_revenue": 0 # TODO: Calculate actual revenue
        },
        "attendees": seats_list # Renamed from seats_detail
    }

    return jsonify({"success": True, "data": dashboard_data}), 200
