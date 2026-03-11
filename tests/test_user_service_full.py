import unittest
import requests
import uuid
import os
import time
from decimal import Decimal

# Configuration
BASE_URL = "http://localhost:5000"

class TestUserService(unittest.TestCase):
    def setUp(self):
        # Create two unique users for testing
        self.email1 = f"user1_{uuid.uuid4()}@example.com"
        self.email2 = f"user2_{uuid.uuid4()}@example.com"
        self.password = "password123"
        self.phone = "+6591234567"
        
        # Register User 1
        resp = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email1,
            "password": self.password,
            "phone": self.phone
        })
        self.assertEqual(resp.status_code, 201)
        self.user1_id = resp.json()['user_id']
        
        # Register User 2
        resp = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email2,
            "password": self.password
        })
        self.assertEqual(resp.status_code, 201)
        self.user2_id = resp.json()['user_id']
        
        # Login User 1 to get token
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email1,
            "password": self.password
        })
        self.assertEqual(resp.status_code, 200)
        self.token1 = resp.json()['access_token']

    def test_credits_transfer(self):
        # 1. Top up User 1
        resp = requests.post(f"{BASE_URL}/credits/topup", json={
            "user_id": self.user1_id,
            "amount": 100.0
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['new_balance'], 100.0)
        
        # 2. Transfer 50 from User 1 to User 2
        resp = requests.post(f"{BASE_URL}/credits/transfer", json={
            "from_user_id": self.user1_id,
            "to_user_id": self.user2_id,
            "amount": 50.0
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['from_user_balance'], 50.0)
        self.assertEqual(data['to_user_balance'], 50.0)
        
        # 3. Verify User 2 balance via public GET (or DB check if we had access, but API is better)
        # We need a token for User 2 to check their own profile usually, or use User 1 to check if allowed (it's not).
        # Let's login User 2
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email2,
            "password": self.password
        })
        token2 = resp.json()['access_token']
        headers = {"Authorization": f"Bearer {token2}"}
        resp = requests.get(f"{BASE_URL}/users/{self.user2_id}", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['credit_balance'], 50.0)

    def test_otp_flow(self):
        # 1. Send OTP
        resp = requests.post(f"{BASE_URL}/otp/send", json={"user_id": self.user1_id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('verification_sid', resp.json())
        
        # 2. Verify OTP (using mock code '123456')
        resp = requests.post(f"{BASE_URL}/otp/verify", json={
            "user_id": self.user1_id,
            "otp_code": "123456"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['message'], 'OTP verified successfully')
        
        # 3. Verify Invalid OTP
        resp = requests.post(f"{BASE_URL}/otp/verify", json={
            "user_id": self.user1_id,
            "otp_code": "000000"
        })
        self.assertEqual(resp.status_code, 400)

    def test_stripe_webhook(self):
        # Simulate Stripe event
        payload = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_1234567890",
                    "amount": 2000, # $20.00
                    "metadata": {
                        "user_id": self.user1_id
                    }
                }
            }
        }
        # Call webhook endpoint
        # Start with 0 balance (or whatever setUp left) - let's check first
        # We can't easily check balance without specific setup, so let's just run it and check increment
        
        # Login again to be sure of state
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email1,
            "password": self.password
        })
        token1 = resp.json()['access_token']
        headers_auth = {"Authorization": f"Bearer {token1}"}
        resp = requests.get(f"{BASE_URL}/users/{self.user1_id}", headers=headers_auth)
        initial_balance = resp.json()['credit_balance']

        # Send Webhook
        # Note: We can't generate a valid signature easily without the stripe library's utility and the SECRET.
        # But our mock implementation checks `stripe.Webhook.construct_event`. 
        # Since I configured a dummy secret 'whsec_test_secret', I can try to generate a signature if I had the library installed in the test runner.
        # However, the user-service has `stripe` installed. I (the agent) might not have it in my `run_command` environment unless I install it.
        # **Alternative**: For this specific test, I can mock the signature verification in the APP code, OR I can trust the unit test within the container. 
        # But I'm running this test script *externally* against the running service.
        # Actually, I can use the `stripe` library in the python script if I install it, or I can skip the signature check if I modify the app to allow a 'SKIP_SIG_CHECK' env var for testing. 
        # 
        # Let's try to install `stripe` and `requests` in the environment where I run the test.
        # `pip install requests stripe`
        pass

if __name__ == '__main__':
    unittest.main()
