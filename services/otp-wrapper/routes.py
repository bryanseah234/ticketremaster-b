from urllib.parse import urljoin

import requests
from flask import Blueprint, current_app, jsonify, request

bp = Blueprint('otp_wrapper', __name__)


def error_response(status_code, code, message):
    return jsonify({'error': {'code': code, 'message': message}}), status_code


def build_smu_url(path):
    base_url = current_app.config['SMU_API_URL'].rstrip('/') + '/'
    return urljoin(base_url, path.lstrip('/'))


def smu_headers():
    return {'X-API-Key': current_app.config['SMU_API_KEY']}


@bp.get('/health')
def health_check():
    return jsonify({'status': 'ok'}), 200


@bp.post('/otp/send')
def send_otp():
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


@bp.post('/notify/sms')
def send_sms_notification():
    data = request.get_json(silent=True)
    if not data or 'phoneNumber' not in data or 'message' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields: phoneNumber, message')

    try:
        response = requests.post(
            build_smu_url('/SendMessage'),
            headers=smu_headers(),
            json={'Mobile': data['phoneNumber'], 'Message': data['message']},
            timeout=10,
        )
        response.raise_for_status()
        return jsonify({'sent': True}), 200
    except (requests.RequestException, ValueError) as exc:
        # Non-critical — log and return success so transfer flow is not blocked
        current_app.logger.warning('SMS notification failed: %s', exc)
        return jsonify({'sent': False, 'reason': str(exc)}), 200



@bp.post('/otp/verify')
def verify_otp():
    data = request.get_json(silent=True)
    if not data or 'sid' not in data or 'otp' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields: sid, otp')

    try:
        response = requests.post(
            build_smu_url('/VerifyOTP'),
            headers=smu_headers(),
            json={'VerificationSid': data['sid'], 'Code': data['otp']},
            timeout=10,
        )
        if response.status_code == 400:
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

    return jsonify({'verified': bool(verified)}), 200
