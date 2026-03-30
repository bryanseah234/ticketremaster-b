"""
Notification Service - WebSocket and Redis Pub/Sub for real-time updates.
Handles real-time event broadcasting across microservices.
"""
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'dev-secret')

# CORS configuration
CORS(app, origins=[
    'http://localhost:5173',
    'http://localhost:3000',
    os.getenv('FRONTEND_URL', 'http://localhost:5173'),
])

# Redis configuration for message broker
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
redis_client = redis.from_url(redis_url)

# Socket.IO configuration
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    message_queue=redis_url,
    channel='socketio',
)

# Sentry initialization
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
try:
    from sentry import init_sentry
    init_sentry(service_name="notification-service")
except ImportError:
    pass  # Sentry not available, continue without it


# ── Event Channels ───────────────────────────────────────────────────────────

EVENT_CHANNELS = {
    'seat_update': 'notifications:seat_update',
    'ticket_update': 'notifications:ticket_update',
    'transfer_update': 'notifications:transfer_update',
    'purchase_update': 'notifications:purchase_update',
    'user_update': 'notifications:user_update',
    'event_update': 'notifications:event_update',
}


# ── WebSocket Event Handlers ─────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect(auth: Optional[Dict] = None):
    """Handle client connection."""
    print(f'[WebSocket] Client connected: {request.sid}')
    emit('connected', {'sid': request.sid})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f'[WebSocket] Client disconnected: {request.sid}')


@socketio.on('subscribe')
def handle_subscribe(data: Dict[str, Any]):
    """Subscribe to a specific channel."""
    channel = data.get('channel')
    if channel and channel in EVENT_CHANNELS:
        join_room(channel)
        print(f'[WebSocket] Client {request.sid} subscribed to {channel}')
        emit('subscribed', {'channel': channel})


@socketio.on('unsubscribe')
def handle_unsubscribe(data: Dict[str, Any]):
    """Unsubscribe from a specific channel."""
    channel = data.get('channel')
    if channel and channel in EVENT_CHANNELS:
        leave_room(channel)
        print(f'[WebSocket] Client {request.sid} unsubscribed from {channel}')


# ── Redis Pub/Sub ────────────────────────────────────────────────────────────

def publish_event(event_type: str, payload: Dict[str, Any], trace_id: Optional[str] = None):
    """
    Publish an event to Redis for cross-service communication.
    Also emits to connected WebSocket clients.
    """
    if event_type not in EVENT_CHANNELS:
        return

    message = {
        'type': event_type,
        'payload': payload,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'traceId': trace_id,
    }

    # Publish to Redis for other services
    channel = EVENT_CHANNELS[event_type]
    redis_client.publish(channel, json.dumps(message))

    # Emit to connected WebSocket clients
    socketio.emit(event_type, message, to=EVENT_CHANNELS[event_type])


def subscribe_to_redis():
    """Background thread to subscribe to Redis channels and forward to WebSocket clients."""
    pubsub = redis_client.pubsub()
    pubsub.psubscribe(EVENT_CHANNELS.values())

    for message in pubsub.listen():
        if message['type'] == 'pmessage':
            try:
                data = json.loads(message['data'])
                event_type = data.get('type')
                if event_type:
                    socketio.emit(event_type, data)
            except json.JSONDecodeError:
                pass


# ── HTTP API Endpoints ───────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'notification-service'}), 200


@app.route('/broadcast', methods=['POST'])
def broadcast():
    """
    Internal endpoint for services to broadcast events.
    Should be called by other microservices via internal network.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': {'code': 'VALIDATION_ERROR', 'message': 'Request body required'}}), 400

    event_type = data.get('type')
    payload = data.get('payload', {})
    trace_id = data.get('traceId')

    if event_type not in EVENT_CHANNELS:
        return jsonify({'error': {'code': 'INVALID_EVENT_TYPE', 'message': f'Unknown event type: {event_type}'}}), 400

    publish_event(event_type, payload, trace_id)

    return jsonify({'message': 'Event broadcasted successfully'}), 200


@app.route('/stats', methods=['GET'])
def stats():
    """Get notification service statistics."""
    return jsonify({
        'connected_clients': len(socketio.server.eio.sockets),
        'channels': list(EVENT_CHANNELS.keys()),
        'redis_connected': redis_client.ping(),
    }), 200


# ── Service Integration Helpers ──────────────────────────────────────────────

def notify_seat_update(seat_data: Dict[str, Any], trace_id: Optional[str] = None):
    """Helper to notify seat updates."""
    publish_event('seat_update', seat_data, trace_id)


def notify_ticket_update(ticket_data: Dict[str, Any], trace_id: Optional[str] = None):
    """Helper to notify ticket updates."""
    publish_event('ticket_update', ticket_data, trace_id)


def notify_transfer_update(transfer_data: Dict[str, Any], trace_id: Optional[str] = None):
    """Helper to notify transfer updates."""
    publish_event('transfer_update', transfer_data, trace_id)


def notify_purchase_update(purchase_data: Dict[str, Any], trace_id: Optional[str] = None):
    """Helper to notify purchase updates."""
    publish_event('purchase_update', purchase_data, trace_id)


# ── Application Entry Point ──────────────────────────────────────────────────

if __name__ == '__main__':
    host = os.getenv('NOTIFICATION_SERVICE_HOST', '0.0.0.0')
    port = int(os.getenv('NOTIFICATION_SERVICE_PORT', '8109'))
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
