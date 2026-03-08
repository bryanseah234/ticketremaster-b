import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"

print("--- Testing Admin Flow ---")

# 1. Login
print("\n1. Logging in as Admin")
login_resp = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "admin@example.com",
    "password": "password123"
})
if login_resp.status_code != 200:
    print(f"Login failed: {login_resp.status_code} {login_resp.text}")
    sys.exit(1)

login_data = login_resp.json()
token = login_data['access_token']
is_admin = login_data['user'].get('is_admin')
print(f"Login successful. is_admin: {is_admin}")
if not is_admin:
    print("User is not admin! Failing.")
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}

# 2. Create Event
print("\n2. Creating new event...")
event_payload = {
    "name": "Admin Test Event",
    "venue": {
        "name": "Test Venue",
        "address": "123 Test St",
        "total_halls": 2
    },
    "hall_id": "HALL-1",
    "event_date": "2026-12-31T20:00:00",
    "total_seats": 250,
    "pricing_tiers": {"CAT1": 100}
}
create_resp = requests.post(f"{BASE_URL}/admin/events", json=event_payload, headers=headers)
if create_resp.status_code != 201:
    print(f"Create event failed: {create_resp.status_code} {create_resp.text}")
    sys.exit(1)

event_data = create_resp.json()['data']
event_id = event_data['event_id']
print(f"Event created successfully: {event_id}. Seats created: {event_data.get('seats_created')}")

# 3. Get Dashboard
print(f"\n3. Getting dashboard for event {event_id}...")
dash_resp = requests.get(f"{BASE_URL}/admin/events/{event_id}/dashboard", headers=headers)
if dash_resp.status_code != 200:
    print(f"Dashboard failed: {dash_resp.status_code} {dash_resp.text}")
    sys.exit(1)

dash_data = dash_resp.json()['data']
print("Dashboard Data:")
print(f"Event Name: {dash_data['name']}")
print(f"Total Seats Available: {dash_data['seats_available']}")
print(f"Total Seats Detail Array Length: {len(dash_data['seats_detail'])}")

print("\nAll tests passed successfully!")
