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
    return {'X-API-KEY': current_app.config['SMU_API_KEY']}


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
            build_smu_url('/SendSMS'),
            headers=smu_headers(),
            json={'phoneNumber': data['phoneNumber']},
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
        return error_response(502, 'OTP_SEND_FAILED', 'SMU response missing verification SID')

    return jsonify({'sid': sid}), 200


@bp.post('/otp/verify')
def verify_otp():
    data = request.get_json(silent=True)
    if not data or 'sid' not in data or 'otp' not in data:
        return error_response(400, 'VALIDATION_ERROR', 'Missing required fields: sid, otp')

    try:
        response = requests.post(
            build_smu_url('/VerifySMS'),
            headers=smu_headers(),
            json={'sid': data['sid'], 'otp': data['otp']},
            timeout=10,
        )
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

    return jsonify({'verified': bool(verified)}), 200
