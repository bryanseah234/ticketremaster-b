---
name: grpc-service
description: TicketRemaster gRPC guidance for Seat Inventory proto changes, stub generation, and safe consumption from orchestrators.
---

# gRPC Service Pattern

## When to Use

Use this skill when updating `proto/seat_inventory.proto`, regenerating Python stubs, or wiring gRPC calls in inventory-dependent modules.

## Architecture Context

- Seat Inventory is the primary gRPC contract in this repository.
- Generated stubs are stored in `shared/grpc/`.
- Consumer modules must copy both generated files together.

## Proto Update Flow

### 1. Edit proto contract

```protobuf
syntax = "proto3";
package seatinventory;

service SeatInventoryService {
  rpc HoldSeat (HoldSeatRequest) returns (HoldSeatResponse);
}
```

### 2. Regenerate stubs into shared folder

```powershell
python -m grpc_tools.protoc -I .\proto --python_out=.\shared\grpc --grpc_python_out=.\shared\grpc .\proto\seat_inventory.proto
```

### 3. Copy to target module

Copy both:
- `shared/grpc/seat_inventory_pb2.py`
- `shared/grpc/seat_inventory_pb2_grpc.py`

## Consumption Pattern

```python
import grpc
from shared.grpc import seat_inventory_pb2, seat_inventory_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = seat_inventory_pb2_grpc.SeatInventoryServiceStub(channel)

response = stub.HoldSeat(
    seat_inventory_pb2.HoldSeatRequest(inventoryId="inv_001", userId="usr_001")
)
```

## References

- [../../../shared/grpc/README.md](../../../shared/grpc/README.md)
- [../../../INSTRUCTION.md](../../../INSTRUCTION.md)
- [../../../TASK.md](../../../TASK.md)
- [../orchestrator-flow/SKILL.md](../orchestrator-flow/SKILL.md)
