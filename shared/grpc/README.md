# Shared gRPC Stubs

This folder contains generated Python stubs from `proto/seat_inventory.proto`.

## Files

- `seat_inventory_pb2.py` — protobuf message classes
- `seat_inventory_pb2_grpc.py` — gRPC client/server bindings

## Generation Command

Run from repository root when the proto contract changes:

```powershell
python -m grpc_tools.protoc -I .\proto --python_out=.\shared\grpc --grpc_python_out=.\shared\grpc .\proto\seat_inventory.proto
```

## Copy Rules

- Copy both generated files into the same target folder.
- Keep both files side-by-side with the code that imports them.
- Regenerate and recopy together to avoid version skew.

## Typical Targets

- `services/seat-inventory-service/`
- `orchestrators/ticket-purchase-orchestrator/`
- `orchestrators/transfer-orchestrator/`
- `orchestrators/ticket-verification-orchestrator/`

## Related Docs

- Shared assets index: [../README.md](../README.md)
- Proto contract location: [../../proto/seat_inventory.proto](../../proto/seat_inventory.proto)
- Orchestrator gRPC usage guidance: [../../.github/skills/grpc-service/SKILL.md](../../.github/skills/grpc-service/SKILL.md)
