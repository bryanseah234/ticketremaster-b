"""
Transfer Service — Order Service (dispute / undo)
Handles transfer lifecycle, disputes, and reversals.

Will handle:
   - create_transfer(seat_id, seller_user_id, buyer_user_id, credits_amount)
   - update_transfer_status(transfer_id, new_status)
   - dispute_transfer(transfer_id, reason)
   - reverse_transfer(transfer_id)
"""
