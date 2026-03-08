# TicketRemaster 🎫

> **IS213 Enterprise Solution Development** — A Microservices-based ticketing platform built for extreme concurrency, strict data consistency, and seamless user experiences.

Welcome to the backend repository of **TicketRemaster**! This platform orchestrates the complete lifecycle of ticket sales, P2P transfers, and venue entry scanning using a blend of highly-performant microservices, asynchronous message queues, and tight data locking mechanisms.

---

## 🏗️ System Architecture

TicketRemaster relies on the **Saga Orchestrator Pattern**. Instead of microservices calling each other in a tangled web (choreography), the **Orchestrator Service** centrally manages all complex distributed transactions.

### High-Level Architecture Flow

```mermaid
graph TD
    Client((Frontend / App)) -->|HTTP/REST| Nginx[API Gateway]
    
    Nginx -->|Routes /api/*| Orch[Orchestrator Service]
    Nginx -->|Routes /api/auth| UserSvc
    Nginx -->|Routes /api/events| EventSvc
    
    Orch -->|gRPC / HTTP2| InvSvc[Inventory Service]
    Orch -->|REST| UserSvc[User Service]
    Orch -->|REST| OrderSvc[Order Service]
    Orch -->|REST| EventSvc[Event Service]
    
    Orch -->|AMQP Publishes TTL Hold| RMQ((RabbitMQ DLX))
    RMQ -->|AMQP Consumes Expiry| InvSvc
    
    UserSvc -->|REST| Stripe[(Stripe API)]
    UserSvc -->|REST| SMU[(SMU 2FA API)]
    
    InvSvc --- DB1[(Seats DB)]
    UserSvc --- DB2[(Users DB)]
    OrderSvc --- DB3[(Orders DB)]
    EventSvc --- DB4[(Events DB)]
    
    classDef external fill:#f9f,stroke:#333,stroke-width:2px;
    class Stripe,SMU external;
```

### Microservices Breakdown

| Service | Protocol | Domain Responsibility |
|---|---|---|
| **API Gateway (Nginx)** | HTTP | Load balancing, rate limiting (100r/m), CORS for `ticketremaster.hong-yi.me`, reverse proxying. |
| **Orchestrator Service** | REST | The "Manager" — handles cross-service flows, triggers compensations on failure, generates Encrypted QR codes. |
| **Inventory Service** | gRPC | Mission critical. Handles pessimistic locking `SELECT FOR UPDATE NOWAIT` for seats. Fast and highly concurrent. |
| **User Service** | REST | Authentication (JWT), Credit balance management, Stripe integration, and SMU OTP 2FA handshakes. |
| **Order Service** | REST | Immutable transaction ledger for purchases and P2P transfers. |
| **Event Service** | REST | Event metadata, venues, halls, pricing. |

---

## 🚀 Quick Start Guide

### 1. Prerequisites

- Docker & Docker Compose
- Python 3.11+ (if running scripts locally)

### 2. Configure Environment

Rename the example environment file and fill in your secrets (e.g., Stripe Keys, JWT secrets, DB passwords).

```bash
git clone <repo-url>
cd ticketremaster-b
cp .env.example .env
```

> **Warning ⚠️:** The `.env.example` may contain default plaintext credentials. For production, **never** commit `.env` files. Use Docker Secrets, AWS Secrets Manager, or Doppler to inject secure keys at runtime.

### 3. Run the Application

Start the entire microservices cluster:

```bash
docker-compose up --build -d
```

All backend services will now be accessible via the API Gateway at `http://localhost:8000`.

### 4. Scale for Traffic Drops (Optional)

If you expect a massive swarm of customers, you can horizontally scale the Orchestrator and Inventory (locking) services. Nginx will automatically Load Balance traffic across all instances.

```bash
docker-compose up -d --scale orchestrator-service=3 --scale inventory-service=2
```

---

## 🚦 Core Scenarios & User Flows

TicketRemaster is designed to handle 3 major business scenarios smoothly, overcoming race conditions and distributed failures.

### 1. Ticket Purchase Flow

**Goal:** Secure a ticket lock instantly, give the user 5 minutes to pay, deduct credits, and generate an encrypted QR code.

```mermaid
sequenceDiagram
    actor User
    participant Orch as Orchestrator
    participant Inv as Inventory (gRPC)
    participant RMQ as RabbitMQ
    participant UserS as User Service
    participant OrderS as Order Service

    User->>Orch: POST /reserve {seat_id}
    Orch->>Inv: ReserveSeat (Pessimistic DB Lock)
    Inv-->>Orch: Success (Seat: HELD)
    Orch->>RMQ: Publish Hold (5-min TTL)
    Orch-->>User: 200 OK (You have 5 mins!)
    
    User->>Orch: POST /pay {order_id}
    Orch->>UserS: Deduct Credits
    UserS-->>Orch: Success
    Orch->>OrderS: Create CONFIRMED Order
    Orch->>Inv: ConfirmSeat
    Inv-->>Orch: Success (Seat: SOLD)
    Orch-->>User: 200 OK + QR Code Payload
```

#### Edge Cases Handled

- **Lock Contention:** If two users click "Reserve" at the exact same millisecond, the DB `NOWAIT` lock grants the seat to only one user instantly. The other receives a `409 SEAT_UNAVAILABLE`.
- **Payment Abandonment:** If the user closes the app and doesn't pay, the message sitting in RabbitMQ expires after 5 minutes and drops into a **Dead Letter Exchange (DLX)**. The Inventory consumer picks it up and resets the seat to `AVAILABLE` automatically.
- **High-Risk Users & Fraud:** If `user.is_flagged = true`, Orchestrator interrupts the `/pay` flow with a `428 OTP_REQUIRED` code. The user must complete an SMU 2FA SMS check before the purchase continues.

---

### 2. Secure P2P Ticket Transfer

**Goal:** Allow users to sell tickets to one another securely, transferring ownership and credits atomically.

```mermaid
sequenceDiagram
    actor Seller
    actor Buyer
    participant Orch as Orchestrator
    participant UserS as User Service
    participant Inv as Inventory
    
    Seller->>Orch: POST /transfer/initiate {seat_id, buyer_id, amount}
    Orch->>UserS: Send OTP to Seller & Buyer
    UserS-->>Seller: SMS Code
    UserS-->>Buyer: SMS Code
    
    Seller->>Orch: POST /transfer/confirm {seller_otp, buyer_otp}
    Buyer->>Orch: (provides OTP offline to Seller)
    Orch->>UserS: Verify OTPs
    UserS->>UserS: Atomic: Buyer Balance -$, Seller Balance +$
    Orch->>Inv: UpdateOwner (Seat -> Buyer)
    Orch-->>Seller: 200 OK Transfer Complete!
```

#### Edge Cases Handled

- **Self-Transfer:** Prevented instantly (`400 SELF_TRANSFER`).
- **Mid-Transfer Sales:** A Unique Partial Index in the Database prevents starting a transfer if one is already `PENDING_OTP`.
- **OTP Failure/Expiry:** If either OTP is wrong or expires, the transfer is suspended. 3 wrong attempts sets the transfer state to `FAILED`.
- **Disputes:** If fraud occurs, support can trigger `/transfer/dispute` to freeze credits, and `/transfer/reverse` to return the ticket to the seller and money to the buyer.

---

### 3. Staff QR Verification

**Goal:** Verify encrypted QR ticket payloads at the venue gate in under 200ms without revealing plaintext ticket IDs.

```mermaid
sequenceDiagram
    actor Staff
    participant Nginx as API Gateway
    participant Orch as Orchestrator
    participant Inv as Inventory
    
    Staff->>Nginx: POST /verify {qr_payload, hall_id}
    Nginx->>Orch: Route
    Orch->>Orch: Decrypt AES-256-GCM
    Orch->>Orch: Check IF (NOW - payload_time) <= 60s
    Orch->>Inv: VerifyTicket & MarkCheckedIn
    Inv-->>Orch: SUCCESS
    Orch-->>Staff: 200 OK (✅ Valid Ticket)
```

#### Edge Cases Handled

- **Screenshot Sharing / Replay Attacks:** The frontend regenerates the QR code every 50 seconds. The backend enforces a strict **60-second TTL**. If a QR is scanned after 60 seconds (like a screenshot sent to a friend), it throws an `EXPIRED` rejection.
- **Counterfeiting / QR Tampering:** The payload is encrypted with `AES-256-GCM` using a secret backend key. Modifying the QR invalidates the cryptographic tag instantly.
- **Wrong Gates:** The QR payload embeds the expected `hall_id`. Scanning at the wrong gate throws a `WRONG_HALL` rejection.
- **Duplicate Scans:** Re-scanning a checked-in ticket returns a `DUPLICATE` alert instantly.

---

## 📚 Further Documentation

For frontend bindings, endpoint structure, and specific configurations, please refer to the documents below:

| Document | Description |
|---|---|
| [FRONTEND.md](FRONTEND.md) | Complete guide for Frontend teams (Vue 3, endpoints, API Gateway routes). |
| [API.md](API.md) | Extensive endpoint dictionary showing JSON inputs and error codes. |
| [INSTRUCTIONS.md](INSTRUCTIONS.md) | Deep-dive into database schema architectures and RabbitMQ configs. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Git workflow and pull request guidelines. |

---

*TicketRemaster Backend Repository — Built for Scale, Optimized for Speed.*
