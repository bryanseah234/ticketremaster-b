from src.models.event import Event
from src.models.venue import Venue
from src.extensions import db
import requests
import os

# Inventory Service HTTP Sidecar URL
# Default to port 8080 as per architecture
INVENTORY_SERVICE_HTTP_URL = os.environ.get('INVENTORY_SERVICE_HTTP_URL', 'http://inventory-service:8080')

def _normalize_category_rows(seat_config):
    if not isinstance(seat_config, dict):
        return {}
    category_rows = seat_config.get("category_rows")
    if not isinstance(category_rows, dict):
        return {}
    normalized = {}
    for category, rows in category_rows.items():
        if isinstance(rows, list):
            normalized[category] = set(str(r) for r in rows)
        elif isinstance(rows, str):
            normalized[category] = {rows}
    return normalized

def _map_seat_category(row_number, category_rows):
    if not category_rows:
        return None
    row_value = str(row_number) if row_number is not None else None
    if not row_value:
        return None
    for category, rows in category_rows.items():
        if row_value in rows:
            return category
    return None

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
    
    try:
        response = requests.get(
            f"{INVENTORY_SERVICE_HTTP_URL}/internal/seats", 
            params={'event_id': str(event_id)}, 
            timeout=2.0
        )
        if response.status_code == 200:
            seats_data = response.json().get('data', [])
            pricing = event_data.get("pricing_tiers") or {}
            category_rows = _normalize_category_rows(event_data.get("seat_config") or {})
            default_category = next(iter(pricing.keys()), None)
            for seat in seats_data:
                category = _map_seat_category(seat.get("row_number"), category_rows) or default_category
                seat["category"] = category
                seat["price"] = pricing.get(category) if category else None
            event_data['seats'] = seats_data
        else:
            print(f"Inventory Service returned {response.status_code}: {response.text}")
            event_data['seats'] = [] 
    except requests.RequestException as e:
        print(f"Error calling Inventory Service: {e}")
        event_data['seats'] = [] # Return empty seats layout on failure
        
    return event_data

def create_event(data):
    venue_data = data.get('venue', {})
    venue = Venue.query.filter_by(name=venue_data.get('name')).first()
    if not venue:
        venue = Venue(
            name=venue_data.get('name'),
            address=venue_data.get('address'),
            total_halls=venue_data.get('total_halls', 1)
        )
        db.session.add(venue)
        db.session.flush()

    event = Event(
        name=data.get('name'),
        venue_id=venue.venue_id,
        hall_id=data.get('hall_id'),
        event_date=data.get('event_date'),
        total_seats=data.get('total_seats'),
        pricing_tiers=data.get('pricing_tiers'),
        seat_selection_mode=data.get('seat_selection_mode') or "SEATMAP",
        seat_config=data.get('seat_config') or {}
    )
    db.session.add(event)
    db.session.commit()
    return event.to_dict()
