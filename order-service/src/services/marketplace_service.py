"""
Marketplace Service — Order Service
Handles CRUD operations for Marketplace Listings.
"""

from db import db
from models.marketplace_listing import MarketplaceListing
import logging

logger = logging.getLogger(__name__)

def create_listing(seat_id: str, seller_user_id: str, asking_price: float) -> MarketplaceListing:
    try:
        # Check if an active/pending listing already exists for this seat
        existing = MarketplaceListing.query.filter_by(seat_id=seat_id).filter(
            MarketplaceListing.status.in_(['ACTIVE', 'PENDING_TRANSFER'])
        ).first()

        if existing:
            return None, "An active or pending listing already exists for this seat."

        listing = MarketplaceListing(
            seat_id=seat_id,
            seller_user_id=seller_user_id,
            asking_price=asking_price,
            status='ACTIVE'
        )
        db.session.add(listing)
        db.session.commit()
        return listing, None
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating listing: {e}")
        return None, str(e)

def get_listing_by_id(listing_id: str) -> MarketplaceListing:
    return MarketplaceListing.query.get(listing_id)

def get_listings(status: str = None, seller_user_id: str = None, seat_id: str = None) -> list:
    query = MarketplaceListing.query
    if status:
        query = query.filter_by(status=status)
    if seller_user_id:
        query = query.filter_by(seller_user_id=seller_user_id)
    if seat_id:
        query = query.filter_by(seat_id=seat_id)
    return query.all()

def update_listing_status(listing_id: str, new_status: str, buyer_user_id: str = None, escrow_transaction_id: str = None) -> MarketplaceListing:
    try:
        listing = MarketplaceListing.query.get(listing_id)
        if not listing:
            return None, "Listing not found"
        
        valid_transitions = {
            'ACTIVE': ['PENDING_TRANSFER', 'CANCELLED'],
            'PENDING_TRANSFER': ['COMPLETED', 'ACTIVE', 'CANCELLED'],
            'COMPLETED': [],
            'CANCELLED': []
        }

        if new_status not in valid_transitions.get(listing.status, []):
            return None, f"Cannot transition listing from {listing.status} to {new_status}"

        # If transitioning to PENDING_TRANSFER, we expect a buyer and transaction
        if new_status == 'PENDING_TRANSFER':
            if buyer_user_id:
                listing.buyer_user_id = buyer_user_id
            if escrow_transaction_id:
                listing.escrow_transaction_id = escrow_transaction_id
            
            if not buyer_user_id:
                 return None, "buyer_user_id required for PENDING_TRANSFER"

        listing.status = new_status
        db.session.commit()
        return listing, None
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating listing status: {e}")
        return None, str(e)
