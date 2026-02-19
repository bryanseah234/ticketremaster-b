from flask import Blueprint, request, jsonify
import requests
import os
import uuid
from src.models.user import User
from src.extensions import db

otp_bp = Blueprint('otp', __name__)

# In-memory storage for VerificationSid (mock implementation for Phase 4)
# In production, use Redis with TTL
verification_store = {}

SMU_API_URL = os.environ.get('SMU_API_URL', 'http://student.smu.edu.sg/api') # Placeholder
SMU_API_KEY = os.environ.get('SMU_API_KEY', 'placeholder-key')

@otp_bp.route('/send', methods=['POST'])
def send_otp():
    """
    Send OTP to user's registered phone
    ---
    tags:
      - OTP
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
          properties:
            user_id:
              type: string
    responses:
      200:
        description: OTP sent successfully
      404:
        description: User not found
      500:
        description: Upstream API error
    """
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
        
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    if not user.phone:
        return jsonify({'error': 'User has no phone number'}), 400
        
    # Call SMU API
    # payload = {'Mobile': user.phone}
    # headers = {'api-key': SMU_API_KEY} # Adjust based on actual SMU API docs
    
    # Mocking the interaction for now as we might not have actual connectivity or credentials in this environment
    # In a real scenario:
    # try:
    #     resp = requests.post(f"{SMU_API_URL}/SendOTP", json=payload, headers=headers)
    #     resp_data = resp.json()
    #     if not resp_data.get('Success'):
    #         return jsonify({'error': resp_data.get('ErrorMessage')}), 500
    #     sid = resp_data.get('VerificationSid')
    # except Exception as e:
    #     return jsonify({'error': str(e)}), 500
    
    # MOCK RESPONSE
    fake_sid = str(uuid.uuid4())
    print(f"DEBUG: Generated Mock VerificationSid {fake_sid} for User {user_id}")
    
    # Store SID mapped to User ID (simplification)
    verification_store[user_id] = fake_sid
    
    return jsonify({'message': 'OTP sent successfully', 'verification_sid': fake_sid}), 200

@otp_bp.route('/verify', methods=['POST'])
def verify_otp():
    """
    Verify OTP code
    ---
    tags:
      - OTP
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - otp_code
          properties:
            user_id:
              type: string
            otp_code:
              type: string
    responses:
      200:
        description: OTP verified
      400:
        description: Invalid or expired OTP
    """
    data = request.get_json()
    user_id = data.get('user_id')
    otp_code = data.get('otp_code')
    
    if not user_id or not otp_code:
        return jsonify({'error': 'Missing user_id or otp_code'}), 400
        
    # Retrieve stored SID
    sid = verification_store.get(user_id)
    if not sid:
        return jsonify({'error': 'No pending OTP verification found for this user'}), 400
        
    # Call SMU API to verify
    # payload = {'VerificationSid': sid, 'Code': otp_code}
    # ... request logic ...
    
    # MOCK LOGIC
    # For testing, let's say '123456' is always the correct code, or any 6 digit code works if we just want to test flow
    if otp_code == '123456':
        # Success
        # Clean up store? Maybe keep it for a bit or rely on overwrite.
        # verification_store.pop(user_id, None) # Optional cleanup
        return jsonify({'message': 'OTP verified successfully'}), 200
    else:
        return jsonify({'error': 'Invalid OTP code'}), 400
