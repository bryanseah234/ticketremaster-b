import requests
import json
import uuid

base_url = "http://localhost:8000/api/auth"
email = f"test_{uuid.uuid4().hex[:6]}@example.com"
password = "password123!"

# 1. Register
reg_data = {
    "email": email,
    "phone": "+6591234567",
    "password": password
}
headers = {
    "apikey": "tk_front_123456789",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

print("--- Registering ---")
r1 = requests.post(f"{base_url}/register", json=reg_data, headers=headers)
print(r1.status_code, r1.text)
user_id = r1.json().get('user_id')

if user_id:
    # 2. Login (Should fail)
    print("\n--- Logging in (should fail) ---")
    r2 = requests.post(f"{base_url}/login", json={"email": email, "password": password}, headers=headers)
    print(r2.status_code, r2.text)

    # 3. Verify OTP
    print("\n--- Verifying OTP (assuming 123456 is mock code) ---")
    r3 = requests.post(f"{base_url}/verify-registration", json={"user_id": user_id, "otp_code": "123456"}, headers=headers)
    print(r3.status_code, r3.text)

    # 4. Login Again
    print("\n--- Logging in again ---")
    r4 = requests.post(f"{base_url}/login", json={"email": email, "password": password}, headers=headers)
    print(r4.status_code, r4.text)
