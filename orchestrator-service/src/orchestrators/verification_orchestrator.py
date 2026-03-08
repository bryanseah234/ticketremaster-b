import os
import json
import base64
import logging
from datetime import datetime, timezone, timedelta
from flask import jsonify
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.utils.grpc_client import inventory_client
from src.utils.http_client import order_service, event_service

logger = logging.getLogger("orchestrator")

# 32-byte hex key or fallback
QR_SECRET = os.environ.get("QR_SECRET_KEY", "0123456789abcdef0123456789abcdef")
try:
    if len(QR_SECRET) == 64:
        aes_key = bytes.fromhex(QR_SECRET)
    else:
        aes_key = QR_SECRET.encode('utf-8')[:32].ljust(32, b'\0')
except:
    aes_key = b'0123456789abcdef0123456789abcdef'

def decrypt_qr_payload(qr_payload_b64):
    try:
        raw = base64.b64decode(qr_payload_b64)
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to decrypt QR: {str(e)}")
        return None

def encrypt_qr_payload(payload_dict):
    try:
        plaintext = json.dumps(payload_dict).encode('utf-8')
        aesgcm = AESGCM(aes_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return base64.b64encode(nonce + ciphertext).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encrypt QR: {str(e)}")
        return None

def handle_verify(qr_payload, hall_id, staff_id):
    try:
        # 1. Decrypt QR
        payload = decrypt_qr_payload(qr_payload)
        if not payload:
            return jsonify({"success": False, "error_code": "QR_INVALID", "message": "Payload tampered or wrong encryption key"}), 400

        seat_id = payload.get("seat_id")
        owner_id = payload.get("owner_id")
        created_at_str = payload.get("created_at")

        # 2. Check TTL (60s)
        try:
            created_at = datetime.fromisoformat(created_at_str)
            if datetime.now(timezone.utc) - created_at > timedelta(seconds=60):
                return jsonify({
                    "success": True,
                    "data": {"result": "EXPIRED", "message": "⏰ Expired QR — Refresh ticket in app"}
                }), 200
        except:
             return jsonify({"success": False, "error_code": "QR_INVALID", "message": "Invalid timestamp format"}), 400

        # 3. Verify ticket via inventory gRPC
        v_res = inventory_client.verify_ticket(seat_id)
        if not v_res.status:
            return jsonify({
                "success": True, 
                "data": {"result": "NOT_FOUND", "message": "🚫 Possible Counterfeit"}
            }), 200
            
        if v_res.status == "HELD":
            return jsonify({
                "success": True,
                "data": {"result": "UNPAID", "message": "❌ Incomplete Payment"}
            }), 200
            
        if v_res.status == "CHECKED_IN":
            return jsonify({
                "success": True,
                "data": {"result": "DUPLICATE", "message": "⚠️ Already Checked In"}
            }), 200

        # Check ownership match
        if v_res.owner_user_id != owner_id:
            return jsonify({
                "success": False,
                "error_code": "NOT_SEAT_OWNER",
                "message": "User_id mismatch from QR payload"
            }), 403

        # 4. Check Hall
        if v_res.event_id:
            ev_res = event_service.get(f"/api/events/{v_res.event_id}")
            if ev_res.status_code == 200:
                ev_data = ev_res.json().get("data", {})
                if ev_data.get("hall_id") != hall_id:
                    return jsonify({
                        "success": True,
                        "data": {"result": "WRONG_HALL", "message": f"🔄 Wrong Hall — Go to Hall {ev_data.get('hall_id')}"}
                    }), 200

        # 5. Mark Checked In
        mark_res = inventory_client.mark_checked_in(seat_id)
        if not mark_res.success:
            return jsonify({
                "success": True,
                "data": {"result": "DUPLICATE", "message": "⚠️ Already Checked In"}
            }), 200

        return jsonify({
            "success": True,
            "data": {
                "result": "SUCCESS",
                "seat_id": seat_id,
                "message": "✅ Valid ticket. Welcome!"
            }
        }), 200

    except Exception as e:
        logger.error(f"Verify error: {str(e)}")
        return jsonify({"success": False, "error_code": "SERVICE_UNAVAILABLE", "message": "Retry scan"}), 503

def handle_get_tickets(user_id):
    res = order_service.get(f"/orders?user_id={user_id}")
    if res.status_code != 200:
        return jsonify(res.json()), res.status_code
        
    orders = res.json()
    tickets = []
    
    for o in orders:
        if o["status"] == "CONFIRMED":
            tickets.append({
                "seat_id": o["seat_id"],
                "status": "SOLD",
                "price_paid": o["credits_charged"]
            })
    return jsonify({"success": True, "data": tickets}), 200

def handle_generate_qr(seat_id, user_id):
    try:
        owner_res = inventory_client.get_seat_owner(seat_id)
        if not owner_res.status:
            return jsonify({"success": False, "error_code": "SEAT_NOT_FOUND", "message": "Seat not found"}), 404
        if owner_res.status != "SOLD":
            return jsonify({"success": False, "error_code": "SEAT_UNAVAILABLE", "message": "Can only generate QR for owned tickets"}), 409
        if owner_res.owner_user_id != user_id:
            return jsonify({"success": False, "error_code": "NOT_SEAT_OWNER", "message": "Not your seat"}), 403
            
        now = datetime.now(timezone.utc)
        payload = {
            "seat_id": seat_id,
            "owner_id": user_id,
            "created_at": now.isoformat()
        }
        qr_string = encrypt_qr_payload(payload)
        
        return jsonify({
            "success": True,
            "data": {
                "qr_payload": qr_string,
                "generated_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=60)).isoformat(),
                "ttl_seconds": 60
            }
        }), 200
    except Exception as e:
        logger.error(f"Generate QR error: {str(e)}")
        return jsonify({"success": False, "error_code": "INTERNAL_ERROR"}), 500
