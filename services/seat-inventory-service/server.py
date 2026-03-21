import os
import threading
from concurrent import futures

import grpc

from app import create_app
from grpc_server import SeatInventoryGrpcService
from seat_inventory_pb2_grpc import add_SeatInventoryServiceServicer_to_server


def run_grpc_server(flask_app):
    grpc_port = int(os.getenv('SEAT_INVENTORY_GRPC_PORT', '50051'))
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    add_SeatInventoryServiceServicer_to_server(SeatInventoryGrpcService(flask_app=flask_app), grpc_server)
    grpc_server.add_insecure_port(f'[::]:{grpc_port}')
    grpc_server.start()
    grpc_server.wait_for_termination()


def run_rest_server(flask_app):
    flask_port = int(os.getenv('PORT', '5000'))
    flask_app.run(host='0.0.0.0', port=flask_port, threaded=True)


def main():
    flask_app = create_app()

    grpc_thread = threading.Thread(target=run_grpc_server, args=(flask_app,), daemon=True)
    rest_thread = threading.Thread(target=run_rest_server, args=(flask_app,), daemon=True)

    grpc_thread.start()
    rest_thread.start()

    grpc_thread.join()
    rest_thread.join()


if __name__ == '__main__':
    main()
