FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY init.sql ./init.sql

# Generate gRPC stubs from proto file
RUN python -m grpc_tools.protoc \
    -I src/proto \
    --python_out=src/proto \
    --grpc_python_out=src/proto \
    src/proto/inventory.proto

# Fix the import in generated grpc stub (uses absolute import by default)
RUN sed -i 's/import inventory_pb2/from src.proto import inventory_pb2/' src/proto/inventory_pb2_grpc.py

EXPOSE 50051
EXPOSE 8080

CMD ["python", "-m", "src.main"]
