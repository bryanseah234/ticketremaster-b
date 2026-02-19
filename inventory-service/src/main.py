"""
Inventory Service — Main entry point
Starts gRPC server + RabbitMQ consumer in a separate daemon thread.
Phase 6: Implement full startup pattern.
See INSTRUCTIONS.md Section 8 for the startup pattern.
"""

import threading


def main():
    # Phase 6: Start gRPC server
    # grpc_server = create_grpc_server()
    # grpc_server.start()

    # Phase 6: Start RabbitMQ consumer in a separate thread
    # consumer_thread = threading.Thread(
    #     target=start_consumer,
    #     args=(db_session_factory,),
    #     daemon=True
    # )
    # consumer_thread.start()

    # Phase 6: Start HTTP health endpoint on port 8080
    # grpc_server.wait_for_termination()

    print("Inventory Service started (placeholder)")


if __name__ == "__main__":
    main()
