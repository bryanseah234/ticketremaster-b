"""
Transfer Service — Order Service (dispute / undo)
Handles transfer lifecycle, disputes, and reversals.
"""
from datetime import datetime, timezone
from db import db
from models.transfer import Transfer

VALID_TRANSITIONS = {
   "INITIATED": {"PENDING_OTP", "FAILED"},
   "PENDING_OTP": {"COMPLETED", "DISPUTED", "FAILED"},
   "COMPLETED": {"REVERSED"},
   "DISPUTED": {"REVERSED", "COMPLETED"},
   "REVERSED": set(),
   "FAILED": set(),
}

def create_transfer(seat_id, seller_user_id, buyer_user_id, initiated_by, credits_amount=None):
   """
   Called by orchestrator during P2P transfer
   Creates the transfer record with status INITATED
   """
   transfer = Transfer(
      seat_id=seat_id,
      seller_user_id=seller_user_id,
      buyer_user_id=buyer_user_id,
      initiated_by=initiated_by,
      credits_amount=credits_amount,
      status="INITIATED",
   )
   db.session.add(transfer)
   db.session.commit()
   return transfer

def get_transfer_by_id(transfer_id):
   return Transfer.query.filter_by(transfer_id=transfer_id).first()

def get_transfers_by_seat(seat_id):
   return Transfer.query.filter_by(seat_id=seat_id).order_by(Transfer.created_at.desc()).all()

def get_transfers_by_user(user_id):
   """
   Returns all transfers where the user is either buyer/seller
   Used to retrieve purchased/sold tickets
   """
   return Transfer.query.filter(
      (Transfer.seller_user_id == user_id) | (Transfer.buyer_user_id == user_id)
   ).order_by(Transfer.created_at.desc()).all()

def update_transfer_status(transfer_id, new_status):
   """
   Advances transfer through its lifecycle
   Called by orchestrator after OTP verification, completion or failure
   """
   transfer = get_transfer_by_id(transfer_id)
   if not transfer:
      return None, "Transfer not found"
   
   allowed = VALID_TRANSITIONS.get(transfer.status, set())
   if new_status not in allowed:
      return None, f"Cannot transition from {transfer.status} to {new_status}"
   
   transfer.status = new_status
   if new_status == "COMPLETED":
      transfer.completed_at = datetime.now(timezone.utc)

   db.session.commit()
   return transfer, None
   
def update_otp_verification(transfer_id, party, verified, verification_sid=None):
   """
   Updates OTP verification status for seller/buyer
   Called by orchestrator after each party's OTP is verified via SMU API

   party: "seller" or "buyer"
   verification_sid: session ID returned by SMU API
   """
   transfer = get_transfer_by_id(transfer_id)
   if not transfer:
      return None, "Transfer not found"
   
   if party == "seller":
      transfer.seller_otp_verified = verified
      if verification_sid:
         transfer.seller_verification_sid = verification_sid
   elif party == "buyer":
      transfer.buyer_otp_verified = verified
      if verification_sid:
         transfer.buyer_verification_sid = verification_sid
   else:
      return None, "Party must be 'seller' or 'buyer'"

   db.session.commit()
   return transfer, None

def dispute_transfer(transfer_id, reason):
   """
   Flags a transfer as disputed. Either party can raise a dispute
   Status must be PENDING_OTP or COMPLETED to be disputed
   """
   transfer = get_transfer_by_id(transfer_id)
   if not transfer:
      return None, "Transfer not found"
   
   if transfer.status not in ("PENDING_OTP", "COMPLETED"):
      return None, f"Cannot dispute a transfer with status {transfer.status}"
   
   transfer.status = "DISPUTED"
   transfer.dispute_reason = reason
   db.session.commit()
   return transfer, None

def reverse_transfer(transfer_id):
   """
   Reverses a completed/disputed transfer
   Orchestrator responsible for reversing credit swap and called Inventory gRPC UpdateOwner
   back to seller
   This function only updates Order Service record
   """
   transfer = get_transfer_by_id(transfer_id)
   if not transfer:
      return None, "Transfer not found"
   
   if transfer.status not in ("COMPLETED", "DISPUTED"):
      return None, f"Cannot reverse a transfer with status {transfer.status}"
   
   transfer.status = "REVERSED"
   db.session.commit()
   return transfer, None