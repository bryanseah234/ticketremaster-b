from src.models.event import Event
from src.extensions import db
import requests
import os

# Inventory Service HTTP Sidecar URL
# Default to port 8080 as per architecture
INVENTORY_SERVICE_HTTP_URL = os.environ.get('INVENTORY_SERVICE_HTTP_URL', 'http://inventory-service:8080')

def get_all_events(page=1, per_page=20):
    pagination = Event.query.paginate(page=page, per_page=per_page, error_out=False)
    
    data = []
    for event in pagination.items:
        # List view usually doesn't need full seat map, just basic info
        # But API.md says nested venue info is required, which models.py handles via to_dict()
        data.append(event.to_dict())
        
    return {
        'data': data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'total_pages': pagination.pages
        }
    }

def get_event_by_id(event_id):
    event = Event.query.get(event_id)
    if not event:
        return None
    
    event_data = event.to_dict()
    
    # Choreography: Fetch seats from Inventory Service
    # Graceful fallback if Inventory Service is unreachable (e.g. not implemented yet)
    try:
        # Timeout set to 2 seconds to avoid blocking for too long
        response = requests.get(
            f"{INVENTORY_SERVICE_HTTP_URL}/internal/seats", 
            params={'event_id': str(event_id)}, 
            timeout=2.0
        )
        if response.status_code == 200:
            seats_data = response.json().get('data', [])
            event_data['seats'] = seats_data
        else:
            print(f"Inventory Service returned {response.status_code}: {response.text}")
            event_data['seats'] = [] 
    except requests.RequestException as e:
        print(f"Error calling Inventory Service: {e}")
        event_data['seats'] = [] # Return empty seats layout on failure
        
    return event_data
