from urllib.parse import urljoin
import logging
import os

import redis
import requests
from flask import Blueprint, current_app, jsonify, request

bp = Blueprint('otp_wrapper', __name__)
logger = logging.getLogger(__name__)


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


def build_smu_url(path):
    base_url = current_app.config['SMU_API_URL'].rstrip('/') + '/'
    return urljoin(base_url, path.lstrip('/'))


def smu_headers():
    return {'X-API-KEY': current_app.config['SMU_API_KEY']}


# Rate limiting configuration
RATE_LIMIT_ATTEMPTS = int(os.environ.get('OTP_RATE_LIMIT_ATTEMPTS', '5'))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('OTP_RATE_LIMIT_WINDOW_SECONDS', '900'))  # 15 minutes
RATE_LIMIT_LOCKOUT_SECONDS = int(os.environ.get('OTP_RATE_LIMIT_LOCKOUT_SECONDS', '900'))  # 15 minutes
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')


def _get_redis_client():
    """Get Redis client for rate limiting."""
    try:
        client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable for rate limiting: %s", exc)
        return None


def _check_rate_limit(phone_number, ip_address=None):
    """
    Check if OTP verification attempts are within rate limits.
    Returns (allowed, attempts, lock_remaining) tuple.
    """
    client = _get_redis_client()
    if client is None:
        # Redis unavailable, allow but log
        return True, 0, 0
    
    # Check phone number rate limit
    phone_key = f"otp:rate:{phone_number}"
    lock_key = f"otp:lock:{phone_number}"
    
    # Check if account is locked
    is_locked = client.get(lock_key)
    if is_locked:
        ttl = client.ttl(lock_key)
        return False, RATE_LIMIT_ATTEMPTS, ttl
    
    # Get current attempt count
    attempts = client.get(phone_key)
    attempts = int(attempts) if attempts else 0
    
    if attempts >= RATE_LIMIT_ATTEMPTS:
        # Lock the account
        client.setex(lock_key, RATE_LIMIT_LOCKOUT_SECONDS, "1")
        return False, attempts, RATE_LIMIT_LOCKOUT_SECONDS
    
    return True, attempts, 0


def _increment_attempt(phone_number):
    """Increment OTP attempt counter."""
    client = _get_redis_client()
    if client is None:
        return 0
    
    phone_key = f"otp:rate:{phone_number}"
    # Increment and set expiry if new key
    pipe = client.pipeline()
    pipe.incr(phone_key)
    pipe.expire(phone_key, RATE_LIMIT_WINDOW_SECONDS)
    pipe.execute()
    
    return int(client.get(phone_key) or 0)


def _reset_attempts(phone_number):
    """Reset OTP attempt counter on successful verification."""
    client = _get_redis_client()
    if client is None:
        return
    
    phone_key = f"otp:rate:{phone_number}"
    lock_key = f"otp:lock:{phone_number}"
    client.delete(phone_key, lock_key)


@bp.get('/health')
def health_check():
    """
    Health check
    ---
    tags:
      - Health
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
    """
    return jsonify({'status': 'ok'}), 200


@bp.post('/otp/send')
def send_otp():
    """
    Send OTP to a phone number
    ---
    tags:
      - OTP
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [phoneNumber]
          properties:
            phoneNumber:
              type: string
              description: Phone number in E.164 format
              example: "+6591234567"
    responses:
      200:
        description: OTP sent
        schema:
          type: object
          properties:
            sid:
              type: string
              description: Verification session ID — pass to /otp/verify
      400:
        description: Missing phoneNumber
      429:
        description: Rate limit exceeded (5 attempts per 15 minutes)
      502:
        description: Upstream SMU API error
    """
    data = request.get_json(silent=True)
    if not data or 'phoneNumber' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'Missing required field: phoneNumber')

    try:
        response = requests.post(
            build_smu_url('/SendOTP'),
            headers=smu_headers(),
            json={'Mobile': data['phoneNumber']},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return error_response(502, 'OTP_SEND_FAILED', str(exc))

    sid = payload.get('verification_sid')
    if sid is None:
        sid = payload.get('verificationSid')
    if sid is None:
        sid = payload.get('sid')
    if sid is None:
        sid = payload.get('VerificationSid')

    if sid is None:
        return error_response(502, 'OTP_SEND_FAILED', 'SMU response missing verification SID')

    return jsonify({'sid': sid}), 200



@bp.post('/otp/verify')
def verify_otp():
    """
    Verify an OTP code
    ---
    tags:
      - OTP
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [sid, otp]
          properties:
            sid:
              type: string
              description: Verification session ID from /otp/send
            otp:
              type: string
              description: OTP code entered by the user
              example: "123456"
            phoneNumber:
              type: string
              description: Phone number (used for rate limiting)
    responses:
      200:
        description: Verification result
        schema:
          type: object
          properties:
            verified:
              type: boolean
      400:
        description: Missing required fields
      429:
        description: Rate limit exceeded
      502:
        description: Upstream SMU API error
    """
    data = request.get_json(silent=True)
    if not data or 'sid' not in data or 'otp' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields: sid, otp')
    
    # Extract phone number for rate limiting (from request headers or data)
    phone_number = data.get('phoneNumber', request.headers.get('X-Phone-Number', 'unknown'))
    ip_address = request.remote_addr
    
    # Check rate limit
    allowed, attempts, lock_remaining = _check_rate_limit(phone_number, ip_address)
    if not allowed:
        if lock_remaining > 0:
            return error_response(429, 'OTP_RATE_LIMIT_EXCEEDED', 
                                f'Account locked. Try again in {lock_remaining} seconds.')
        else:
            return error_response(429, 'OTP_RATE_LIMIT_EXCEEDED',
                                f'Rate limit exceeded. {RATE_LIMIT_ATTEMPTS - attempts} attempts remaining.')

    try:
        response = requests.post(
            build_smu_url('/VerifyOTP'),
            headers=smu_headers(),
            json={'VerificationSid': data['sid'], 'Code': data['otp']},
            timeout=10,
        )
        if response.status_code == 400:
            # Invalid OTP - increment attempt counter
            new_attempts = _increment_attempt(phone_number)
            
            if new_attempts >= RATE_LIMIT_ATTEMPTS:
                return error_response(429, 'OTP_RATE_LIMIT_EXCEEDED',
                                    f'Maximum attempts reached. Account locked for {RATE_LIMIT_LOCKOUT_SECONDS} seconds.')
            
            return jsonify({'verified': False}), 200
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return error_response(502, 'OTP_VERIFY_FAILED', str(exc))

    verified = payload.get('verified')
    if verified is None:
        verified = payload.get('is_verified')
    if verified is None:
        verified = payload.get('isVerified')
    if verified is None:
        verified = payload.get('success')
    if verified is None:
        verified = payload.get('Success')

    if verified:
        # Success - reset attempt counter
        _reset_attempts(phone_number)

    return jsonify({'verified': bool(verified)}), 200
