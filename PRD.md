# Product Requirements Document (PRD): TicketRemaster

## Executive Summary
TicketRemaster is a highly scalable, microservices-driven backend platform designed to manage the end-to-end lifecycle of event ticketing, peer-to-peer (P2P) transfers, secure venue access, and credit-based payments. Operating on a robust architecture of decoupled Flask services and edge Orchestrators, the system guarantees high concurrency, data consistency through pessimistic locking, and fault-tolerant asynchronous event handling. The platform ensures a secure and seamless experience for event-goers and staff while providing extensible integrations with external providers like Stripe, OutSystems, and SMU Notification APIs.

## System Architecture & Data Flow
TicketRemaster employs an Orchestrator-driven microservices architecture to manage business logic across 12 isolated atomic services and 8 specialized orchestrators.
- **API Gateway (Kong):** Serves as the single entry point for all frontend and external traffic, routing requests to the appropriate orchestrator.
- **Orchestrator Layer:** Stateless Flask applications that compose complex business flows (e.g., `ticket-purchase-orchestrator`, `transfer-orchestrator`). They handle JWT validation, execute distributed sagas, and aggregate data from atomic services.
- **Atomic Service Layer:** Domain-specific Flask services, each backed by its own isolated PostgreSQL database, ensuring strict data encapsulation (e.g., `user-service`, `ticket-service`, `seat-inventory-service`).
- **Data Flow & Inter-Service Communication:**
  - **REST (HTTP):** Standard synchronous communication between orchestrators and atomic services.
  - **gRPC:** High-throughput, low-latency communication utilized exclusively between the `ticket-purchase-orchestrator` and `seat-inventory-service` to manage pessimistic row-level locking during seat holds.
  - **Asynchronous Queues (RabbitMQ):** Used for non-blocking workflows. Seat holds publish a TTL message; upon expiration, a Dead Letter Exchange (DLX) triggers a background thread to release the seat. Additionally, it handles seller notifications during P2P transfers.
- **External Integrations:** Credit balances are offloaded to an external OutSystems application. Payments are processed via Stripe (with webhooks verifying signatures). OTPs are dispatched via the SMU Notification API.

## Comprehensive Feature Matrix
### Core Functionality
- **Identity & Access Management:**
  - JWT-based stateless authentication via `auth-orchestrator`.
  - Passwords hashed using `bcrypt` and stored securely with individual salts.
  - Role-based access control distinguishing between `user`, `staff`, and `admin`. Staff tokens encapsulate `venueId` to restrict verification scopes.
- **Inventory & Purchasing:**
  - **Seat Holding:** Utilizes `SELECT ... FOR UPDATE` pessimistic locking in the `seat-inventory-service` via gRPC to prevent double-booking.
  - **Automated Hold Expiry:** RabbitMQ TTL queues paired with a DLX consumer to automatically release orphaned seat holds after a configurable duration (e.g., 600 seconds).
  - **Credit Transactions:** OutSystems API integration for real-time balance checks and deductions, with a local `credit-transaction-service` maintaining an immutable audit ledger. Stripe webhook integrations handle top-ups securely.
- **Marketplace & P2P Transfers:**
  - Users can list active tickets on a public marketplace via `marketplace-orchestrator`.
  - **Transfer Saga Pattern:** `transfer-orchestrator` manages multi-step, multi-party transfers. Requires buyer OTP verification, followed by seller OTP verification. Executes an atomic swap of credits and ticket ownership with built-in compensating actions (rollback) if any intermediate step fails.
- **Venue Access & Verification:**
  - **Dynamic QR Codes:** `qr-orchestrator` generates short-lived (60s TTL), SHA-256 hashed QR codes securely signed with a backend `QR_SECRET`.
  - **Ticket Scanning:** `ticket-verification-orchestrator` validates the QR TTL, confirms seat sold status, verifies venue alignment, and logs the scan to prevent duplicate entries.

### Deprecated/Altered Features
- **Local Credit Balances:** The original scope likely included local credit management. This was altered; credit balances are now definitively managed by an external OutSystems instance to centralize financial state. The local database only acts as a transaction log.
- **Synchronous Expiry Sweepers:** Replaced by RabbitMQ DLX queues to decouple the hold expiry logic, dramatically improving system performance and reliability under high load.
- **Monolithic Endpoints:** Direct frontend-to-service communication was entirely deprecated in favor of an Orchestrator pattern, enforcing strict boundary layers and preventing unauthorized direct database mutations.

## Non-Functional Requirements
- **Scalability:** The strict database-per-service isolation allows horizontal scaling of heavy-load components like the `seat-inventory-service`. Orchestrators are fully stateless and containerized.
- **Performance:** Gunicorn with multi-threading (4 workers) and parallel execution of gRPC/REST servers inside the `seat-inventory-service` ensures concurrent request handling without serialization bottlenecks.
- **Security:** Strict separation of external and internal networks. Stripe webhooks require signature verification. Sensitive configurations (e.g., `JWT_SECRET`, `STRIPE_SECRET_KEY`) are environment-injected.
- **Fault Tolerance:** Distributed transactions use the Saga pattern with compensating rollbacks (e.g., restoring OutSystems balances if a ticket transfer fails midway). Idempotency checks prevent double-crediting from redundant Stripe webhooks.

## Future Roadmap
- **Kubernetes Migration (Phase 8):** Transitioning from `docker-compose` to Minikube/K8s with Horizontal Pod Autoscalers (HPA) targeting 70% CPU utilization, and centralizing environment variables into Kubernetes Secrets.
- **Caching Layer:** Implementing Redis for read-heavy, low-mutation endpoints like `/events` and `/venues` to reduce PostgreSQL load.
- **End-to-End Business Journeys:** Expanding test coverage from atomic unit tests to comprehensive Postman-driven E2E integration suites validating cross-orchestrator workflows.
