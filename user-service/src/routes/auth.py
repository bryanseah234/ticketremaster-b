from flask import Blueprint, request, jsonify
import re
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from src.models.user import User
from src.extensions import db
import datetime

auth_bp = Blueprint('auth', __name__)



@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user
    ...
    """
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password') or not data.get('phone'):
        return jsonify({'error': 'Missing email, phone, or password'}), 400

    # Validation
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, data['email']):
        return jsonify({'error': 'Invalid email format'}), 400
        
    if len(data['password']) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409

    new_user = User(
        email=data['email'],
        phone=data.get('phone')
    )
    new_user.set_password(data['password'])

    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Database error', 'details': str(e)}), 500

    import requests
    try:
        from src.routes.otp import SMU_API_URL, SMU_API_KEY, verification_store
        payload = {'Mobile': new_user.phone}
        headers = {'X-Contacts-Key': SMU_API_KEY}
        resp = requests.post(f"{SMU_API_URL}/SendOTP", json=payload, headers=headers)
        resp_data = resp.json()
        if resp_data.get('Success'):
            verification_store[str(new_user.user_id)] = resp_data.get('VerificationSid')
            return jsonify({
                'message': 'OTP sent to phone',
                'status': 'PENDING_VERIFICATION',
                'user_id': str(new_user.user_id)
            }), 201
        else:
            return jsonify({'error': 'Failed to send OTP upon registration', 'details': resp_data.get('ErrorMessage')}), 500
    except Exception as e:
        return jsonify({'error': 'Error contacting SMS gateway', 'details': str(e)}), 500



@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and return tokens
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
            password:
              type: string
    responses:
      200:
        description: Login successful
      401:
        description: Invalid credentials
    """
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Missing email or password'}), 400

    user = User.query.filter_by(email=data['email']).first()
    
    if user and user.check_password(data['password']):
        if not user.is_verified:
            return jsonify({'error': 'UNVERIFIED_ACCOUNT', 'message': 'Please verify your phone number before logging in.'}), 403
        # Create tokens
        # Identity can be user_id
        access_token = create_access_token(
            identity=str(user.user_id), 
            expires_delta=datetime.timedelta(hours=6),
            additional_claims={"iss": "ticketremaster", "is_admin": user.is_admin}
        )
        refresh_token = create_refresh_token(
            identity=str(user.user_id), 
            expires_delta=datetime.timedelta(days=7),
            additional_claims={"iss": "ticketremaster", "is_admin": user.is_admin}
        )
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 200
    
    return jsonify({'error': 'Invalid email or password'}), 401

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token
    ---
    tags:
      - Auth
    security:
      - Bearer: []
    responses:
      200:
        description: New access token
      401:
        description: Invalid refresh token
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    new_access_token = create_access_token(
        identity=current_user_id, 
        expires_delta=datetime.timedelta(hours=6),
        additional_claims={"iss": "ticketremaster", "is_admin": user.is_admin if user else False}
    )
    return jsonify({'access_token': new_access_token}), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout user (Revoke token)
    ---
    tags:
      - Auth
    security:
      - Bearer: []
    responses:
      200:
        description: Logout successful
    """
    from src.extensions import BLOCKLIST
    from flask_jwt_extended import get_jwt
    
    jti = get_jwt()['jti']
    BLOCKLIST.add(jti)
    
    return jsonify({'message': 'Logout successful'}), 200

@auth_bp.route('/verify-registration', methods=['POST'])
def verify_registration():
    """
    Verify OTP sent during registration
    """
    data = request.get_json()
    user_id = data.get('user_id')
    otp_code = data.get('otp_code')
    
    if not user_id or not otp_code:
        return jsonify({'error': 'Missing user_id or otp_code'}), 400
        
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    try:
        from src.routes.otp import SMU_API_URL, SMU_API_KEY, verification_store
        import requests
        
        sid = verification_store.get(str(user_id))
        if not sid:
            return jsonify({'error': 'No pending OTP verification found for this user'}), 400
            
        payload = {'VerificationSid': sid, 'Code': otp_code}
        headers = {'X-Contacts-Key': SMU_API_KEY}
        
        resp = requests.post(f"{SMU_API_URL}/VerifyOTP", json=payload, headers=headers)
        resp_data = resp.json()
        if resp_data.get('Success'):
            verification_store.pop(str(user_id), None)
            
            # verify user
            user.is_verified = True
            db.session.commit()
            
            # auto-login
            access_token = create_access_token(
                identity=str(user.user_id), 
                expires_delta=datetime.timedelta(hours=6),
                additional_claims={"iss": "ticketremaster", "is_admin": user.is_admin}
            )
            refresh_token = create_refresh_token(
                identity=str(user.user_id), 
                expires_delta=datetime.timedelta(days=7),
                additional_claims={"iss": "ticketremaster", "is_admin": user.is_admin}
            )
            
            return jsonify({
                'message': 'Registration verified successfully. Logged in.',
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user.to_dict()
            }), 200
        else:
            return jsonify({'error': resp_data.get('ErrorMessage') or 'Invalid OTP code'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
