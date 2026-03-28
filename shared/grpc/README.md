# Shared gRPC Stubs

This directory serves as the centralized output location for Python gRPC stubs generated from the `proto/seat_inventory.proto` contract. 

In the TicketRemaster architecture, gRPC is used exclusively for high-performance, low-latency communication with the `seat-inventory-service`. This ensures that pessimistic row-level database locks for seat reservations are executed instantly, avoiding the overhead of standard HTTP REST calls during high-concurrency checkout flows.

## Files in this Directory

- `seat_inventory_pb2.py`: Contains the compiled Protocol Buffer message classes (e.g., `HoldSeatRequest`, `HoldSeatResponse`).
- `seat_inventory_pb2_grpc.py`: Contains the generated gRPC client stubs (`SeatInventoryServiceStub`) and server servicers (`SeatInventoryServiceServicer`).

## The Protocol Buffer Contract

The source of truth is located at `../../proto/seat_inventory.proto`. It defines four critical RPC methods for managing seat state:

1. **`HoldSeat`**: Attempts to place a pessimistic lock on a seat. Returns a `hold_token` and a `held_until` timestamp if successful.
2. **`ReleaseSeat`**: Manually releases a hold before the TTL expires. Requires the `hold_token` for authorization.
3. **`SellSeat`**: Transitions a held seat to a `sold` state. Requires the `hold_token`.
4. **`GetSeatStatus`**: A fast, read-only check to verify the current state (`available`, `held`, `sold`) of a specific seat.

## Generation Command

If you modify `proto/seat_inventory.proto`, you **must** regenerate these files. 

Run the following command from the **repository root**:

```powershell
python -m grpc_tools.protoc -I .\proto --python_out=.\shared\grpc --grpc_python_out=.\shared\grpc .\proto\seat_inventory.proto
```

*Note: Ensure your virtual environment has `grpcio` and `grpcio-tools` installed before running this command.*

## Usage & Copy Rules

Python's gRPC implementation relies on absolute module imports. To avoid `ModuleNotFoundError` issues across different Docker containers, **do not symlink** these files. 

Instead, whenever you regenerate the stubs, **copy both files directly** into the root directory of any service that requires them.

### Target Destinations:

**The Server:**
- `services/seat-inventory-service/` (Implements `SeatInventoryServiceServicer`)

**The Clients:**
- `orchestrators/ticket-purchase-orchestrator/` (Calls `HoldSeat`, `SellSeat`, `GetSeatStatus`)
- `orchestrators/transfer-orchestrator/` (May call `GetSeatStatus`)
- `orchestrators/ticket-verification-orchestrator/` (May call `GetSeatStatus`)

**Important:** Always copy both `seat_inventory_pb2.py` and `seat_inventory_pb2_grpc.py` together to prevent version skew between the message definitions and the client/server bindings.

## Client Implementation Example

When implementing a client in an orchestrator, set up the channel using environment variables:

```python
import grpc
import seat_inventory_pb2
import seat_inventory_pb2_grpc
import os

host = os.environ.get("SEAT_INVENTORY_GRPC_HOST", "seat-inventory-service")
port = os.environ.get("SEAT_INVENTORY_GRPC_PORT", "50051")
channel = grpc.insecure_channel(f"{host}:{port}")

stub = seat_inventory_pb2_grpc.SeatInventoryServiceStub(channel)

# Example call
response = stub.GetSeatStatus(
    seat_inventory_pb2.GetSeatStatusRequest(inventory_id="inv_001")
)
```

## Related Documentation

- Proto contract location: [../../proto/seat_inventory.proto](../../proto/seat_inventory.proto)
- Orchestrator gRPC usage guidance: [../../.github/skills/grpc-service/SKILL.md](../../.github/skills/grpc-service/SKILL.md)
